"""Restore an exported public archive into isolated memory and verify its evidence."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def verify_export(path):
    database = sqlite3.connect(":memory:")
    try:
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
