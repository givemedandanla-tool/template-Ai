"""Data-only checkpoint adapter: include public QA journals without changing tested application/tools.

The existing collector predates .jsonl evidence. Reuse the original prepare/archive/
readback protocol, adding real bytes and Git blob hashes before checkpoint creation.
This never edits a previous checkpoint or evidence run and never waives an attachment.
Move .jsonl into the default collector during the next planned code change/regression.
"""
import argparse,hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import dev_checkpoint
from dev_common import manifest


def with_journals(root):
    files=manifest(root)
    for path in sorted((Path(root)/'docs/evidence/runs').rglob('*.jsonl')):
        if path.is_symlink():raise ValueError('Public evidence journal cannot be a symbolic link')
        data=path.read_bytes()
        for line in data.splitlines():json.loads(line)
        files[path.relative_to(root).as_posix()]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),git_blob_sha1=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest())
    return dict(sorted(files.items()))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--id',required=True);parser.add_argument('--base-commit',required=True);parser.add_argument('--summary',required=True);parser.add_argument('--next',required=True);parser.add_argument('--requirements',nargs='*',default=[]);args=parser.parse_args()
    dev_checkpoint.manifest=with_journals
    record=dev_checkpoint.prepare(ROOT,args.id,args.base_commit,args.summary,args.next,args.requirements)
    print(json.dumps(dict(id=record['id'],phase=record['phase'],files=len(record['source_files']),journal_paths=[name for name in record['source_files'] if name.endswith('.jsonl')])))
