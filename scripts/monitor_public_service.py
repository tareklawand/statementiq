"""Bounded public-site/data checks. Runs periodically; no financial values are repaired."""
import argparse
import json
import math
import time
from urllib.request import Request, urlopen

ORIGIN='https://statementiq-lb.com'


def read(url,timeout=90):
    with urlopen(Request(url,headers={'User-Agent':'StatementIQ availability monitor'}),timeout=timeout) as response:
        return response.read()


def monitor(wait_seconds=0, reader=read):
    deadline=time.monotonic()+wait_seconds
    while True:
        try:
            html=reader(ORIGIN+'/').decode()
            if 'StatementIQ' not in html or 'data-tab="tab5"' not in html:raise ValueError('Published DCF page is not available')
            status=json.loads(reader(ORIGIN+'/api/research/status'))
            if status.get('status')!='ready':raise ValueError('Filing archive is not ready')
            baseline=json.loads(reader(ORIGIN+'/api/research/model-baseline?ticker=AAPL'))
            if baseline.get('symbol')!='AAPL' or baseline.get('status')!='ready':raise ValueError('Default-company model baseline is unavailable')
            analysis=json.loads(reader(ORIGIN+'/api/analyze?ticker=AAPL'))
            raw=analysis.get('metrics',{}).get('raw_financials',{})
            if analysis.get('symbol')!='AAPL' or any(not isinstance(raw.get(key),(int,float)) or not math.isfinite(raw[key]) or raw[key]<=0 for key in ('revenue','total_assets')):
                raise ValueError('Default-company statement figures are missing or invalid')
            hold=analysis.get('data_quality',{}).get('integrity_hold_reason')
            if hold:raise ValueError('Financial integrity requires review: '+hold)
            return {'status':'ready','model_baseline_period':baseline['period'],'statement_provider':analysis['data_quality'].get('statement_provider')}
        except Exception:
            if time.monotonic()>=deadline:raise
            time.sleep(min(20,max(deadline-time.monotonic(),0)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--wait-seconds',type=int,default=0)
    print(json.dumps(monitor(parser.parse_args().wait_seconds)))
