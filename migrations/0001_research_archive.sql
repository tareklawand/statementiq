CREATE TABLE IF NOT EXISTS filing_snapshots (
  id TEXT PRIMARY KEY CHECK(length(id) = 64),
  symbol TEXT NOT NULL,
  cik TEXT NOT NULL,
  accession TEXT NOT NULL,
  report_period TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  methodology_version TEXT NOT NULL,
  methodology_sha256 TEXT NOT NULL,
  payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE INDEX IF NOT EXISTS snapshots_symbol_time ON filing_snapshots(symbol, observed_at DESC, id);
CREATE INDEX IF NOT EXISTS snapshots_cik_accession ON filing_snapshots(cik, accession);
CREATE TRIGGER IF NOT EXISTS snapshots_no_update BEFORE UPDATE ON filing_snapshots
BEGIN SELECT RAISE(ABORT, 'Snapshots are append-only'); END;
CREATE TRIGGER IF NOT EXISTS snapshots_no_delete BEFORE DELETE ON filing_snapshots
BEGIN SELECT RAISE(ABORT, 'Snapshots are append-only'); END;

CREATE TABLE IF NOT EXISTS filing_watch (
  symbol TEXT PRIMARY KEY,
  cik TEXT NOT NULL,
  accession TEXT NOT NULL,
  report_period TEXT NOT NULL,
  last_checked_at TEXT NOT NULL,
  last_requested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS watch_check_time ON filing_watch(last_checked_at);

CREATE TABLE IF NOT EXISTS ingestion_runs (
  id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL CHECK(status IN ('running', 'unchanged', 'archived', 'unavailable')),
  snapshot_id TEXT,
  reason TEXT
);
CREATE INDEX IF NOT EXISTS ingestion_symbol_time ON ingestion_runs(symbol, started_at DESC);
