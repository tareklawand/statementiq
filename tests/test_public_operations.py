import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from backup_public_archive import backup
from verify_archive_backup import verify_export
from monitor_public_service import monitor


def evidence():
    return {'purpose':'public_sec_filing_evidence','symbol':'EXAMPLE','info':{'price':None},'data_quality':{'sec_filing':{'cik':'0000123456','accession_number':'test-accession','report_period':'2025-12-31'}}}


def test_public_backup_is_verified_and_restores_without_credentials(tmp_path):
    content=json.dumps(evidence(),sort_keys=True).encode();snapshot_id=hashlib.sha256(content).hexdigest()
    record={'id':snapshot_id,'symbol':'EXAMPLE','cik':'0000123456','accession':'test-accession','report_period':'2025-12-31',
        'observed_at':'2026-01-01T00:00:00Z','methodology_version':'test','methodology_sha256':'a'*64}
    def get(url):
        return json.dumps({'as_of':'2026-01-01T00:00:00Z','snapshots':[record],'next_cursor':None}).encode() if '/catalog' in url else content
    output=tmp_path/'backup.tar.gz'
    assert backup(output,fetcher=get)['snapshots']==1
    assert verify_export(output)['verified_snapshots']==1
    assert output.with_suffix('.gz.sha256').exists()
    def corrupted(url):
        return get(url) if '/catalog' in url else b'{}'
    original=output.read_bytes()
    with pytest.raises(ValueError,match='checksum'):backup(output,fetcher=corrupted)
    assert output.read_bytes()==original


def test_monitor_requires_real_inputs_and_never_clears_a_hold():
    def get(url):
        if url.endswith('/'):return b'StatementIQ data-tab="tab5"'
        if '/status' in url:return b'{"status":"ready"}'
        if '/startup-config' in url:return b'{"startup_url":"https://statementiq-sacc.onrender.com/health"}'
        if url=='https://statementiq-sacc.onrender.com/health':return b'{"status":"healthy","service":"StatementIQ Engine"}'
        if '/model-baseline' in url:return b'{"symbol":"AAPL","status":"ready","period":"2026-09-26"}'
        return json.dumps({'symbol':'AAPL','metrics':{'raw_financials':{'revenue':100,'total_assets':200}},'data_quality':{'statement_provider':'SEC'}}).encode()
    assert monitor(reader=get)['status']=='ready'
    def held(url):
        body=get(url)
        if '/analyze' in url:
            value=json.loads(body);value['data_quality']['integrity_hold_reason']='Newest filing is not indexed';return json.dumps(value).encode()
        return body
    with pytest.raises(ValueError,match='requires review'):monitor(reader=held)
