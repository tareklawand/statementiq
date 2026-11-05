"""Restore an exported public archive into isolated memory and verify its evidence."""
import argparse
import hashlib
import json
import sqlite3
import tarfile
from pathlib import Path


def verify_export(path):
    database = sqlite3.connect(":memory:")
    try:
        if str(path).endswith(('.tar.gz','.tgz')):
            database.executescript((Path(__file__).resolve().parents[1]/'migrations/0001_research_archive.sql').read_text())
            with tarfile.open(path,'r:gz') as archive:
                manifest=json.load(archive.extractfile('manifest.json'))
                records=manifest['snapshots']
                assert records and len(records)<=10000,'Empty or oversized archive manifest'
                seen=set()
                for record in records:
                    snapshot_id=record['id']
                    assert len(snapshot_id)==64 and all(c in '0123456789abcdef' for c in snapshot_id) and snapshot_id not in seen,'Invalid snapshot ID'
                    seen.add(snapshot_id)
                    content=archive.extractfile('snapshots/'+snapshot_id+'.json').read(1_000_001)
                    assert len(content)<=1_000_000 and hashlib.sha256(content).hexdigest()==snapshot_id,'Snapshot checksum mismatch'
                    data=json.loads(content)
                    filing=data['data_quality']['sec_filing']
                    assert data.get('purpose')=='public_sec_filing_evidence' and filing['report_period']==record['report_period'],'Unexpected snapshot scope or reporting period'
                    database.execute('INSERT INTO filing_snapshots(id,symbol,cik,accession,report_period,observed_at,methodology_version,methodology_sha256,payload) VALUES(?,?,?,?,?,?,?,?,?)',
                        (snapshot_id,record['symbol'],record['cik'],record['accession'],record['report_period'],record['observed_at'],record['methodology_version'],record['methodology_sha256'],content.decode()))
        else:
            database.executescript(Path(path).read_text())
        assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity check failed"
        count = 0
        for snapshot_id, symbol, cik, accession, body in database.execute("SELECT id,symbol,cik,accession,payload FROM filing_snapshots"):
            assert hashlib.sha256(body.encode()).hexdigest() == snapshot_id, f"Checksum mismatch: {snapshot_id}"
            data = json.loads(body)
            filing = data["data_quality"]["sec_filing"]
            assert data["symbol"] == symbol and filing["cik"] == cik and filing["accession_number"] == accession
            count += 1
        return {"sqlite_integrity": "ok", "verified_snapshots": count, "restore_target": "isolated memory only"}
    finally:
        database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sql_export")
    print(json.dumps(verify_export(parser.parse_args().sql_export)))
