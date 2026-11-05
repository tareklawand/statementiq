from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
import threading
import pytest
import pandas as pd
from fastapi.testclient import TestClient
import data_fetcher
import main


def test_concurrent_startup_and_visitor_loads_share_one_source_fetch(monkeypatch):
    started=threading.Event();waiters=threading.Event();release=threading.Event();lock=threading.Lock()
    counts={'fetch':0,'waiters':0}
    expected={'symbol':'EXAMPLE','income_stmt':{'reported_revenue':123},'error':None}
    class ObservedFuture(Future):
        def result(self,*args,**kwargs):
            with lock:
                counts['waiters']+=1
                if counts['waiters']==3:waiters.set()
            return super().result(*args,**kwargs)
    def retrieve(symbol,force_refresh):
        counts['fetch']+=1;started.set()
        assert release.wait(2)
        return expected
    monkeypatch.setattr(data_fetcher,'Future',ObservedFuture)
    monkeypatch.setattr(data_fetcher,'_fetch_stock_data',retrieve)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(data_fetcher.fetch_stock_data,'example') for _ in range(4)]
        try:assert started.wait(1) and waiters.wait(1)
        finally:release.set()
        assert [job.result() for job in jobs]==[expected]*4
    assert counts['fetch']==1


def test_main_analysis_does_not_wait_for_annual_text_and_review_is_still_available(monkeypatch):
    stock={'symbol':'EXAMPLE','fetched_at':datetime.now(timezone.utc).isoformat(),
        'sec_filing':{'key_filings':{'annual':{'filing_url':'https://www.sec.gov/Archives/example.htm'}}}}
    monkeypatch.setattr(main,'fetch_stock_data',lambda *args,**kwargs:stock)
    def build(data,symbol,**kwargs):
        assert kwargs['include_filing_review'] is False
        return {'symbol':symbol,'metrics':{'reported_revenue':123}}
    monkeypatch.setattr(main,'build_analysis_payload',build)
    monkeypatch.setattr(main,'scan_annual_filing',lambda *args:pytest.fail('Report text cannot delay the dashboard'))
    response=TestClient(main.app).get('/api/analyze?ticker=EXAMPLE')
    assert response.status_code==200 and response.json()['metrics']['reported_revenue']==123
    assert response.json()['filing_disclosure_review']['status']=='deferred'
    assert 'sources;dur=' in response.headers['server-timing']
    monkeypatch.setattr(main,'scan_annual_filing',lambda url:{'status':'analyzed','topics':[]})
    review=TestClient(main.app).get('/api/research/filing-review?ticker=EXAMPLE').json()
    assert review['review']['status']=='analyzed' and review['filing_url'].endswith('example.htm')


def test_edge_cache_cannot_extend_the_original_source_freshness(monkeypatch):
    monkeypatch.setattr(main.time,'time',lambda:1000)
    assert main.analysis_cache_deadline({'fetched_at':'1970-01-01T00:15:00+00:00'})=='1200'
    assert main.analysis_cache_deadline({'fetched_at':'1970-01-01T01:00:00+00:00'})=='0'
    assert main.analysis_cache_deadline({})=='0'


def test_complete_primary_quotes_do_not_download_unused_fallbacks():
    class Primary:
        @property
        def fast_info(self):pytest.fail('Complete primary quote must not invoke fallback quotes')
        def history(self,**kwargs):pytest.fail('Complete primary quote must not download a year of prices')
        def get_history_metadata(self):pytest.fail('Reported quote timestamp must not be fetched again')
    values={'regularMarketPrice':100,'previousClose':99,'marketCap':1000,'sharesOutstanding':10,
        'currency':'USD','exchange':'NMS','quoteType':'EQUITY','fiftyTwoWeekHigh':120,'fiftyTwoWeekLow':80,
        'dividendRate':0,'targetMeanPrice':110,'regularMarketTime':1790000000}
    info=data_fetcher._enrich_info_with_live_market_fallbacks(Primary(),values)
    assert all(info[key]==value for key,value in values.items())


def test_complete_same_period_annual_preserves_reported_eps_without_using_old_values():
    period=pd.Timestamp('2025-12-31')
    annual=pd.DataFrame({period:[100,20,2]},index=['Total Revenue','Net Income','Diluted EPS'])
    ttm=pd.DataFrame({period:[100,20]},index=['Total Revenue','Net Income'])
    selected,basis=data_fetcher._select_flow_statement(ttm,annual)
    assert basis=='latest_annual' and selected.at['Diluted EPS',period]==2
    newer=ttm.rename(columns={period:pd.Timestamp('2026-03-31')})
    selected,basis=data_fetcher._select_flow_statement(newer,annual)
    assert basis=='trailing_twelve_months' and 'Diluted EPS' not in selected.index
    ttm.at['Net Income',period]=21
    assert data_fetcher._select_flow_statement(ttm,annual)[1]=='trailing_twelve_months'
