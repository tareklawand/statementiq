"""Read-only public endpoint diagnosis. No credentials or financial values are logged."""
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def diagnose():
    endpoints = [
        ('published_page', 'https://statementiq-lb.com/'),
        ('public_archive', 'https://statementiq-lb.com/api/research/status'),
        ('proxied_health', 'https://statementiq-lb.com/health'),
        ('dcf_baseline', 'https://statementiq-lb.com/api/research/model-baseline?ticker=AAPL'),
        ('company_analysis', 'https://statementiq-lb.com/api/analyze?ticker=AAPL'),
        ('origin_health', 'https://statementiq-sacc.onrender.com/health'),
        ('origin_dcf_baseline', 'https://statementiq-sacc.onrender.com/api/research/model-baseline?ticker=AAPL'),
    ]
    for stage, url in endpoints:
        started = time.monotonic()
        record = {'stage': stage}
        try:
            request = Request(url, headers={'User-Agent': 'StatementIQ availability monitor', 'Accept': 'application/json,text/html'})
            try:
                response = urlopen(request, timeout=40)
            except HTTPError as error:
                response = error
            with response:
                record['http_status'] = response.code
                record['headers'] = {name: response.headers.get(name) for name in (
                    'content-type', 'retry-after', 'cf-ray', 'x-statementiq-request-id', 'rndr-id', 'server-timing')
                    if response.headers.get(name)}
                body = response.read(65536)
                if 'json' in response.headers.get('content-type', ''):
                    try:
                        value = json.loads(body)
                        record['response'] = {key: value[key] for key in ('status', 'code', 'request_id') if key in value}
                    except (ValueError, TypeError):
                        record['body_format'] = 'large_json_prefix_not_logged' if len(body)==65536 else 'invalid_json'
                elif 'html' in response.headers.get('content-type', ''):
                    record['body_format'] = 'html'
        except (URLError, TimeoutError, OSError) as error:
            record['network_error'] = type(error).__name__
        record['elapsed_seconds'] = round(time.monotonic() - started, 3)
        print(json.dumps(record), flush=True)


if __name__ == '__main__':
    diagnose()
