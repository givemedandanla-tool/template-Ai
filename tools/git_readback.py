"""使用現有 Git proxy 讀回 checkpoint；不需要抽取 token 或假稱 REST API。

每次重新 fetch 遠端分支，再從讀回的 commit/tree 逐檔核對。
只產生 metadata 與新收據；不 reset、不改 origin、不合併、不推送。
"""
import argparse
from pathlib import Path
import re
import subprocess

from dev_checkpoint import acknowledge
from dev_common import ROOT, write_json


def readback(root=ROOT, remote='origin', ref='refs/heads/dev/v0.1-first-version', checkpoint_id=None):
    root = Path(root).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}', remote) or not ref.startswith('refs/heads/'):
        raise ValueError('使用已設定的 remote 名稱與完整分支 ref，不傳入 token 或網址')
    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=True)
        return result.stdout
    git('check-ref-format', ref)
    git('fetch', '--no-tags', remote, ref)
    sha = git('rev-parse', '--verify', 'FETCH_HEAD^{commit}').decode().strip()
    head = git('rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    if sha != head:
        raise ValueError('目前 HEAD 與剛讀回的遠端分支不同；不寫確認收據')
    tree_sha = git('rev-parse', sha+'^{tree}').decode().strip()
    entries = []
    for raw in git('ls-tree', '-r', '-z', sha).split(b'\0'):
        if not raw:
            continue
        meta, path = raw.split(b'\t', 1)
        mode, kind, blob = meta.decode().split()
        entries.append(dict(path=path.decode(), mode=mode, type=kind, sha=blob))
    folder = root / '.checkpoints/native-readback'
    method = 'NATIVE_GIT_FETCH_AND_EXACT_TREE_BLOB_READBACK'
    commit = dict(sha=sha, tree=dict(sha=tree_sha), verification_source=method)
    tree = dict(sha=tree_sha, tree=entries, truncated=False, verification_source=method)
    write_json(folder/'commit.json', commit)
    write_json(folder/'tree.json', tree)
    receipt = None
    if checkpoint_id:
        receipt = acknowledge(root, checkpoint_id, folder/'commit.json', folder/'tree.json',
            verification='Native Git: fresh origin fetch, exact HEAD/tree and every checkpoint Git blob SHA; no REST API claim')
    return dict(commit=sha, tree=tree_sha, files=len(entries), method=method,
                checkpoint=checkpoint_id, receipt=receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--ref', default='refs/heads/dev/v0.1-first-version')
    parser.add_argument('--checkpoint')
    args = parser.parse_args()
    import json
    result = readback(remote=args.remote, ref=args.ref, checkpoint_id=args.checkpoint)
    print(json.dumps({key: value for key, value in result.items() if key != 'receipt'}))


if __name__ == '__main__':
    main()
