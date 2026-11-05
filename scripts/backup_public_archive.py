"""Verified offsite-ready backup of public SEC snapshots; no credentials or private data."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ORIGIN='https://statementiq-lb.com'
HASH=re.compile(r'^[a-f0-9]{64}$')
MAX_BACKUP_BYTES=15*1024*1024


def get(url):
    error=None
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={'User-Agent':'StatementIQ public archive backup','Accept':'application/json'}),timeout=90) as response:
                content=response.read(1_100_000)
                if len(content)>1_000_000:raise ValueError('Snapshot response exceeds archive size limit')
                return content
        except Exception as exc:
            error=exc
            if attempt<2:time.sleep(5*(attempt+1))
    raise RuntimeError('Public archive request failed') from error


def backup(output, origin=ORIGIN, fetcher=get):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    cursor=None;as_of=None;records=[];seen=set()
    for page in range(101):
        query={}
        if cursor:query['cursor']=cursor
        if as_of:query['as_of']=as_of
        payload=json.loads(fetcher(origin+'/api/research/catalog'+('?' + urlencode(query) if query else '')))
        if as_of and payload['as_of']!=as_of:raise ValueError('Archive observation cutoff changed during backup')
        as_of=payload['as_of']
        for row in payload['snapshots']:
            if not HASH.fullmatch(row['id']) or row['id'] in seen:raise ValueError('Invalid or duplicate snapshot identifier')
            seen.add(row['id']);records.append(row)
        cursor=payload.get('next_cursor')
        if not cursor:break
    else:raise ValueError('Archive exceeds the bounded backup record limit; no partial backup is published')
    if not records:raise ValueError('Archive is empty; refusing to publish an empty replacement backup')
    temporary=output.with_suffix('.pending')
    try:
        with tarfile.open(temporary,'w:gz') as archive:
            manifest={'as_of':as_of,'origin':origin,'scope':'Public SEC filing snapshots only; operational logs, private models and notes are excluded.','snapshots':records}
            content=json.dumps(manifest,sort_keys=True).encode()
            entry=tarfile.TarInfo('manifest.json');entry.size=len(content);archive.addfile(entry,io.BytesIO(content))
            for row in records:
                content=fetcher(origin+'/api/research/snapshots/'+row['id']+'?format=canonical')
                if hashlib.sha256(content).hexdigest()!=row['id']:raise ValueError('Snapshot checksum failed')
                evidence=json.loads(content)
                filing=evidence['data_quality']['sec_filing']
                if evidence.get('purpose')!='public_sec_filing_evidence' or evidence['symbol']!=row['symbol'] or filing['cik']!=row['cik'] or filing['accession_number']!=row['accession'] or evidence['info'].get('price') is not None:
                    raise ValueError('Snapshot is not the expected public SEC-only evidence')
                entry=tarfile.TarInfo('snapshots/'+row['id']+'.json');entry.size=len(content);archive.addfile(entry,io.BytesIO(content))
        if temporary.stat().st_size>MAX_BACKUP_BYTES:raise ValueError('Backup exceeds the free-storage safety cap; no partial artifact is published')
        temporary.replace(output)
        output.with_suffix(output.suffix+'.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'\n')
        return {'snapshots':len(records),'compressed_bytes':output.stat().st_size,'as_of':as_of}
    finally:
        temporary.unlink(missing_ok=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default='archive/public-sec-evidence.tar.gz');parser.add_argument('--origin',default=ORIGIN)
    args=parser.parse_args();print(json.dumps(backup(args.output,args.origin)))
