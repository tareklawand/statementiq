import json
from pathlib import Path
import sys
from email.message import Message

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import data_fetcher
import main
import sec_facts_validator
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from monitor_public_service import EndpointError, monitor, retry_after_seconds


def available(url):
    if url.endswith('/'): return b'StatementIQ data-tab="tab5"'
    if '/status' in url: return b'{"status":"ready"}'
    if '/model-baseline' in url: return b'{"symbol":"AAPL","status":"ready","period":"2026-09-26"}'
    return json.dumps({'symbol':'AAPL','metrics':{'raw_financials':{'revenue':100,'total_assets':200}},
                       'data_quality':{'statement_provider':'SEC'}}).encode()


def test_monitor_respects_rate_limits_and_identifies_the_failing_stage():
    clock=[0]; records=[]; calls=[]; waits=[]
    def get(url):
        calls.append((url,clock[0]))
        if '/model-baseline' in url and clock[0]<120:
            headers=Message();headers['Retry-After']='120';headers['x-statementiq-request-id']='trace-123'
            raise EndpointError(429,headers,b'{"code":"upstream_temporarily_unavailable","cookie":"must never be logged"}')
        return available(url)
    def sleep(seconds):waits.append(seconds);clock[0]+=seconds
    assert monitor(300,get,clock=lambda:clock[0],sleeper=sleep,reporter=records.append)['status']=='ready'
    assert waits==[120]
    assert records[0]['stage']=='dcf_baseline' and records[0]['http_status']==429
    assert records[0]['trace']=={'x-statementiq-request-id':'trace-123'}
    assert 'must never' not in json.dumps(records)


def test_monitor_keeps_alerting_when_a_cooldown_exceeds_its_budget():
    def get(url):
        if '/model-baseline' in url:raise EndpointError(429,{'Retry-After':'3600'})
        return available(url)
    with pytest.raises(EndpointError):
        monitor(600,get,clock=lambda:0,sleeper=lambda seconds:pytest.fail('Cannot ignore or shorten the cooldown'))
    assert retry_after_seconds('Sat, 07 Nov 2026 15:02:00 GMT',now=1794063600)==120
    assert retry_after_seconds('nan')==retry_after_seconds('-10')==0


def test_backup_does_not_depend_on_analysis_and_still_verifies_checksums():
    workflow=(Path(__file__).parents[1]/'.github/workflows/research-operations.yml').read_text()
    backup=workflow.split('  public-sec-backup:',1)[1]
    assert 'needs:' not in backup and 'verify_archive_backup.py' in backup
    assert "github.event.schedule == '0 1 * * *'" in backup
    assert 'persist-credentials: false' in backup and 'retention-days: 7' in backup


def test_temporary_source_failures_are_retryable_across_analysis_model_review_and_reports(monkeypatch):
    failed={'error':'Financial source unavailable','error_code':'source_temporarily_unavailable','retryable':True,'retry_after_seconds':42}
    monkeypatch.setattr(main,'fetch_stock_data',lambda *args,**kwargs:failed)
    client=TestClient(main.app)
    responses=[client.get(path+'?ticker=EXAMPLE') for path in ('/api/analyze','/api/research/model-baseline','/api/research/filing-review')]
    responses.append(client.post('/api/download-pdf',json={'symbol':'EXAMPLE'}))
    for response in responses:
        assert response.status_code==503 and response.headers['retry-after']=='42'
        assert response.headers['cache-control']=='no-store'
        assert response.json()['detail']=='Financial source unavailable'
    failed.update(retryable=False,error_code='unsupported_security')
    response=client.get('/api/analyze?ticker=SPY')
    assert response.status_code==400 and 'retry-after' not in response.headers


def test_failure_cooldown_starts_at_completion_and_forced_refresh_respects_it(monkeypatch):
    clock=[100]; calls=[]
    class Broken:
        def __init__(self,symbol):calls.append(symbol);clock[0]=200;raise RuntimeError('Provider failed slowly')
    monkeypatch.setattr(data_fetcher,'_CACHE',{})
    monkeypatch.setattr(data_fetcher.time,'time',lambda:clock[0])
    monkeypatch.setattr(data_fetcher.yf,'Ticker',Broken)
    first=data_fetcher.fetch_stock_data('OUTAGE',force_refresh=True)
    assert first['error'] and first['retryable']
    clock[0]=201
    second=data_fetcher.fetch_stock_data('OUTAGE',force_refresh=True)
    assert second['retry_after_seconds']==59 and calls==['OUTAGE']
    assert second['income_stmt'].empty and second['info']['data_source']=='unavailable'


def test_hosting_head_probes_work_without_financial_provider_calls(monkeypatch):
    monkeypatch.setattr(main,'fetch_stock_data',lambda *args,**kwargs:pytest.fail('Liveness must not fetch prices'))
    client=TestClient(main.app)
    for path in ('/','/health'):
        response=client.head(path)
        assert response.status_code==200 and response.content==b''


def test_same_period_changed_provider_values_and_new_filings_invalidate_sec_matches(monkeypatch):
    import requests
    requests_seen=[]
    date=pd.Timestamp('2026-06-30')
    income=pd.DataFrame({date:[100]},index=['Total Revenue'])
    balance=pd.DataFrame({date:[200]},index=['Total Assets'])
    payload={'facts':{'us-gaap':{'Assets':{'units':{'USD':[{'val':200,'end':'2026-06-30','form':'10-Q','accn':'first'}]}}}}}
    class Response:
        def raise_for_status(self):pass
        def json(self):return payload
    monkeypatch.setattr(sec_facts_validator,'_CACHE',{})
    monkeypatch.setattr(requests,'get',lambda *args,**kwargs:(requests_seen.append(1) or Response()))
    first=sec_facts_validator.validate_core_sec_facts('123',income,balance,'USD','first')
    assert first['status']=='matched'
    balance.loc['Total Assets',date]=500
    second=sec_facts_validator.validate_core_sec_facts('123',income,balance,'USD','first')
    assert second['status']=='mismatch' and len(requests_seen)==2
    payload['facts']['us-gaap']['Assets']['units']['USD'][0].update(val=500,accn='amendment')
    third=sec_facts_validator.validate_core_sec_facts('123',income,balance,'USD','amendment')
    assert third['status']=='matched' and len(requests_seen)==3
