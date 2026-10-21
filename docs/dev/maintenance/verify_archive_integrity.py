"""Read-only integrity follow-up. Does not extract, delete, upload or approve cleanup."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import zipfile

ROOT=Path(__file__).resolve().parents[3]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-seconds',type=int,default=600)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Keep existing observations immutable')
    inventory=ROOT/'docs/dev/maintenance/STORAGE_CHECKPOINT_INVENTORY_20261021.csv'
    with inventory.open(encoding='utf-8-sig') as stream:
        rows=[r for r in csv.DictReader(stream) if r['recommendation']=='CONDITIONAL_OLD_COPY_REQUIRES_HASH_AND_RESTORE_CHECK' and r['is_symlink']=='False']
    started=time.monotonic();results=[]
    def save():
        value=dict(observed_utc=datetime.now(timezone.utc).isoformat(),scope='READ_ONLY_ARCHIVE_SHA256_AND_ZIP_CRC_NOT_RESTORE_OR_DELETION_APPROVAL',
            expected=len(rows),completed=len(results),results=results,elapsed_seconds=round(time.monotonic()-started,3),deleted_files=0,
            full_restore='NOT_EXECUTED',unique_content_and_remote_blob_recovery='NOT_EXECUTED')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    for row in rows:
        if time.monotonic()-started>=args.max_seconds:break
        checkpoint=row['checkpoint']
        if not checkpoint.startswith('CP-') or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in checkpoint):raise ValueError('Unsafe checkpoint ID')
        path=ROOT/row['path']
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT/'.checkpoints'):raise ValueError('Unexpected archive location')
        record=json.loads((ROOT/'docs/checkpoints'/(checkpoint+'.json')).read_text())
        expected=record['local_snapshot']['sha256']
        if record['local_snapshot']['path']!=row['path']:raise ValueError('Inventory/record path mismatch')
        sha=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):sha.update(block)
        observed=sha.hexdigest()
        try:
            with zipfile.ZipFile(path) as archive:
                members=len(archive.infolist())
                crc='PASS' if archive.testzip() is None else 'FAIL'
        except zipfile.BadZipFile:
            members=None;crc='FAIL_BAD_ZIP'
        results.append(dict(checkpoint=checkpoint,bytes=path.stat().st_size,expected_sha256=expected,observed_sha256=observed,
            hash_status='PASS' if observed==expected else 'FAIL',zip_crc=crc,members=members))
        save()
        print(json.dumps(dict(completed=len(results),expected=len(rows),hash_status=results[-1]['hash_status'],zip_crc=crc)),flush=True)
    save()

if __name__=='__main__':main()
