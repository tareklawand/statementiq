"""Failure-path tests: no live traffic, provider fixtures or load on production."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import anyio
import httpx
import pytest
import requests
from starlette.responses import Response

import main
import data_fetcher
import filing_disclosure_analyzer as disclosures
import sec_filing_validator as filings
from resource_limits import ExpensiveRequestLimit
from model_requests import ModelRequestLimit
from source_limits import read_bounded, read_json


def test_health_remains_available_when_sync_workers_are_occupied():
    async def check():
        limiter=anyio.to_thread.current_default_thread_limiter()
        previous=limiter.total_tokens;limiter.total_tokens=1
        started=threading.Event();release=threading.Event()
        def blocked_work():started.set();release.wait(3)
        worker=asyncio.create_task(anyio.to_thread.run_sync(blocked_work))
        try:
            while not started.is_set():await asyncio.sleep(.001)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://test') as client:
                for path in ('/health','/api/presets'):
                    response=await asyncio.wait_for(client.get(path),timeout=.5)
                    assert response.status_code==200
        finally:
            release.set();await worker;limiter.total_tokens=previous
    asyncio.run(check())


def test_expensive_work_is_bounded_without_blocking_health_and_slots_recover():
    async def check():
        started=asyncio.Event();release=asyncio.Event();calls=[]
        async def app(scope,receive,send):
            calls.append(scope['path'])
            if scope['path']=='/api/analyze':started.set();await release.wait()
            await Response('ready')(scope,receive,send)
        guarded=ExpensiveRequestLimit(app,max_active=1)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=guarded),base_url='http://test') as client:
            first=asyncio.create_task(client.get('/api/analyze'));await started.wait()
            try:
                busy=await asyncio.wait_for(client.get('/api/research/model-baseline'),.5)
                assert busy.status_code==503 and busy.headers['retry-after']=='5'
                assert busy.headers['cache-control']=='no-store'
                assert '/api/research/model-baseline' not in calls
                assert (await client.get('/health')).status_code==200
            finally:release.set();await first
            assert (await client.get('/api/research/model-baseline')).status_code==200
    asyncio.run(check())


def test_document_slots_cover_filing_review_and_exports_and_release_on_error():
    async def check():
        started=asyncio.Event();release=asyncio.Event()
        async def app(scope,receive,send):
            if scope['path']=='/api/research/filing-review':started.set();await release.wait();raise RuntimeError('source failed')
            await Response('ready')(scope,receive,send)
        guarded=ExpensiveRequestLimit(app,max_active=4,max_documents=1)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=guarded,raise_app_exceptions=False),base_url='http://test') as client:
            first=asyncio.create_task(client.get('/api/research/filing-review'));await started.wait()
            try:
                assert (await client.post('/api/research/export-model')).status_code==503
                assert (await client.get('/api/analyze')).status_code==200
            finally:release.set();await first
            assert (await client.post('/api/research/export-model')).status_code==200
    asyncio.run(check())


class Stream:
    def __init__(self,chunks,headers=None):
        self.chunks=chunks;self.headers=headers or {};self.closed=False;self.reads=0
    def raise_for_status(self):pass
    def iter_content(self,chunk_size):
        for value in self.chunks:self.reads+=1;yield value
    def close(self):self.closed=True


@pytest.mark.parametrize('headers',[{}, {'Content-Length':'1'}, {'Content-Encoding':'gzip','Content-Length':'1'}])
def test_oversized_decoded_streams_stop_before_the_rest_is_downloaded(headers):
    response=Stream([b'1234',b'5678',b'must not be read'],headers)
    with pytest.raises(ValueError,match='size limit'):read_bounded(response,7)
    assert response.reads==2 and response.closed


def test_declared_oversized_bodies_are_rejected_without_a_download():
    response=Stream([b'must not be read'],{'Content-Length':'100'})
    with pytest.raises(ValueError):read_bounded(response,8)
    assert response.reads==0 and response.closed


def test_bounded_json_keeps_exact_values_and_closes_broken_streams():
    response=Stream([b'{"reported":',b'123.45}'])
    assert read_json(response)=={'reported':123.45} and response.closed
    response=Stream([b'not json'])
    with pytest.raises(ValueError):read_json(response)
    assert response.closed


def test_large_json_histories_are_not_buffered_in_parallel():
    first_started=threading.Event();second_started=threading.Event();release=threading.Event()
    class First(Stream):
        def iter_content(self,chunk_size):
            first_started.set();assert release.wait(2);yield b'{}'
    class Second(Stream):
        def iter_content(self,chunk_size):second_started.set();yield b'{}'
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(read_json,First([]));assert first_started.wait(1)
        two=pool.submit(read_json,Second([]))
        try:assert not second_started.wait(.05)
        finally:release.set()
        assert one.result()==two.result()=={}


def test_filing_metadata_and_phrase_review_caches_remain_bounded(monkeypatch):
    monkeypatch.setattr(filings,'_FILING_CACHE',{})
    monkeypatch.setattr(disclosures,'_CACHE',{})
    class EmptyFilings:
        def raise_for_status(self):pass
        def json(self):return {'filings':{'recent':{}}}
    monkeypatch.setattr(filings.requests,'get',lambda *a,**k:EmptyFilings())
    for i in range(100):filings.get_latest_sec_filing('EXAMPLE'+str(i),cik_hint='123')
    assert len(filings._FILING_CACHE)==filings.MAX_FILING_CACHE_ENTRIES
    class Filing(Stream):encoding='utf-8';status_code=200
    monkeypatch.setattr(disclosures.requests,'get',lambda *a,**k:Filing([b'<p>Critical audit matter</p>']))
    for i in range(50):assert disclosures.scan_annual_filing('https://www.sec.gov/Archives/'+str(i)+'.htm')['status']=='analyzed'
    assert len(disclosures._CACHE)==disclosures._MAX_CACHE_ENTRIES


def test_failed_review_cooldown_begins_when_the_attempt_finishes(monkeypatch):
    clock=[100];calls=[]
    monkeypatch.setattr(disclosures,'_CACHE',{})
    monkeypatch.setattr(disclosures.time,'time',lambda:clock[0])
    def fail(*args,**kwargs):calls.append(1);clock[0]=200;raise requests.Timeout('slow source')
    monkeypatch.setattr(disclosures.requests,'get',fail)
    url='https://www.sec.gov/Archives/example.htm'
    assert disclosures.scan_annual_filing(url)['status']=='unavailable'
    clock[0]=201
    assert disclosures.scan_annual_filing(url)['status']=='unavailable' and len(calls)==1


def test_source_admission_has_no_unbounded_queue_and_cached_data_stays_available(monkeypatch):
    from concurrent.futures import Future
    import time
    monkeypatch.setattr(data_fetcher,'_INFLIGHT',{'ONE':Future(),'TWO':Future()})
    cached={'symbol':'CACHED','error':None}
    monkeypatch.setattr(data_fetcher,'_CACHE',{'CACHED':{'timestamp':time.time(),'data':cached}})
    monkeypatch.setattr(data_fetcher._SOURCE_POOL,'submit',lambda *args:pytest.fail('No unbounded provider queue'))
    assert data_fetcher.fetch_stock_data('THIRD')['error_code']=='source_busy'
    assert len(data_fetcher._INFLIGHT)==2
    assert data_fetcher.fetch_stock_data('CACHED') is cached


def test_slow_uploads_cannot_occupy_the_service_forever():
    async def check():
        async def app(*args):pytest.fail('Incomplete body cannot start financial work')
        async def receive():await asyncio.Event().wait()
        messages=[]
        async def send(message):messages.append(message)
        guarded=ModelRequestLimit(app,max_body_seconds=.02)
        await guarded({'type':'http','method':'POST','path':'/api/research/forecast'},receive,send)
        assert messages[0]['status']==408
    asyncio.run(check())


def test_pdf_bodies_have_the_same_preparse_size_limit_as_model_requests():
    async def check():
        async def app(*args):pytest.fail('Oversized body cannot fetch statements or build a PDF')
        async def receive():return {'type':'http.request','body':b'x'*1024,'more_body':False}
        messages=[]
        async def send(message):messages.append(message)
        await ModelRequestLimit(app,max_bytes=100)({'type':'http','method':'POST','path':'/api/download-pdf'},receive,send)
        assert messages[0]['status']==413
    asyncio.run(check())
