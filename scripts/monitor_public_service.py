"""Bounded public checks with stage-level diagnostics and respectful recovery."""
import argparse
from datetime import timezone
from email.utils import parsedate_to_datetime
import json
import math
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ORIGIN='https://statementiq-lb.com'
TRANSIENT={408,425,429,500,502,503,504,520,521,522,523,524}


def retry_after_seconds(value, now=None):
    if not value:return 0
    try:seconds=float(value)
    except (ValueError,TypeError):
        try:
            date=parsedate_to_datetime(value)
            if date.tzinfo is None:date=date.replace(tzinfo=timezone.utc)
            seconds=date.timestamp()-(time.time() if now is None else now)
        except (ValueError,TypeError,OverflowError):return 0
    return max(0,seconds) if math.isfinite(seconds) else 0


class EndpointError(Exception):
    def __init__(self,status,headers=None,body=b''):
        self.status=status;headers=headers or {}
        self.retry_after=retry_after_seconds(headers.get('Retry-After'))
        self.trace={}
        for key in ('x-statementiq-request-id','cf-ray','rndr-id'):
            value=headers.get(key)
            if value and re.fullmatch(r'[A-Za-z0-9._:-]{1,160}',value):self.trace[key]=value
        # Retain public machine codes only, never a raw provider error page,
        # cookies, credentials or financial response values in public logs.
        try:code=json.loads(body).get('code')
        except (ValueError,TypeError,AttributeError):code=None
        self.code=code if isinstance(code,str) and re.fullmatch(r'[a-z_]{1,80}',code) else None
        super().__init__(f'HTTP {status}')


def read(url,timeout=90):
    try:
        with urlopen(Request(url,headers={'User-Agent':'StatementIQ availability monitor','Accept':'application/json,text/html'}),timeout=timeout) as response:
            return response.read()
    except HTTPError as error:
        with error:raise EndpointError(error.code,error.headers,error.read(16384)) from None


def monitor(wait_seconds=0,reader=read,*,clock=time.monotonic,sleeper=time.sleep,reporter=None):
    deadline=clock()+wait_seconds;attempt=0
    while True:
        attempt+=1;stage='published_page'
        try:
            def get(path):
                # Actual network calls share the total recovery deadline;
                # injected readers preserve their simple one-argument API.
                timeout=min(90,max(.1,deadline-clock())) if wait_seconds else 90
                return reader(ORIGIN+path,timeout=timeout) if reader is read else reader(ORIGIN+path)
            html=get('/').decode()
            if 'StatementIQ' not in html or 'data-tab="tab5"' not in html:raise ValueError('Published DCF page is not available')
            stage='public_archive';status=json.loads(get('/api/research/status'))
            if status.get('status')!='ready':raise ValueError('Filing archive is not ready')
            stage='company_analysis';analysis=json.loads(get('/api/analyze?ticker=AAPL'))
            raw=analysis.get('metrics',{}).get('raw_financials',{})
            if analysis.get('symbol')!='AAPL' or any(type(raw.get(key)) not in (int,float) or not math.isfinite(raw[key]) or raw[key]<=0 for key in ('revenue','total_assets')):
                raise ValueError('Default-company statement figures are missing or invalid')
            hold=analysis.get('data_quality',{}).get('integrity_hold_reason')
            if hold:raise ValueError('Financial integrity requires review: '+hold)
            stage='dcf_baseline';baseline=json.loads(get('/api/research/model-baseline?ticker=AAPL'))
            if baseline.get('symbol')!='AAPL' or baseline.get('status')!='ready':raise ValueError('Default-company model baseline is unavailable')
            if reporter:reporter({'event':'public_service_check','stage':'complete','status':'ready','attempt':attempt})
            return {'status':'ready','model_baseline_period':baseline['period'],'statement_provider':analysis['data_quality'].get('statement_provider')}
        except Exception as error:
            retry_after=getattr(error,'retry_after',0);http_status=getattr(error,'status',None)
            record={'event':'public_service_check','stage':stage,'status':'failed','attempt':attempt,'error_type':type(error).__name__}
            if http_status is not None:
                record.update(http_status=http_status,retry_after_seconds=retry_after,trace=getattr(error,'trace',{}))
                if getattr(error,'code',None):record['response_code']=error.code
            elif isinstance(error,ValueError):record['detail']=str(error)[:400]
            if reporter:reporter(record)
            remaining=deadline-clock()
            if remaining<=0 or (http_status is not None and http_status not in TRANSIENT):raise
            cooldown=max(retry_after,60 if http_status==429 else min(30,5*2**min(attempt-1,3)))
            # Never shorten an upstream cooldown to fit our remaining budget.
            if cooldown>=remaining:raise
            sleeper(cooldown)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--wait-seconds',type=int,default=0)
    print(json.dumps(monitor(parser.parse_args().wait_seconds,reporter=lambda record:print(json.dumps(record),flush=True))))
