"""Set the pinned bootloader's documented interpreter option; preserve product bytes."""
import argparse
import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]

def configure(*,baseline=False):
    path=ROOT/'build/release/TemplateAI.spec';text=path.read_text(encoding='utf-8')
    needle='EXE(pyz, a.scripts, [], exclude_binaries=True'
    if text.count(needle)!=1 or text.count('runtime_hooks=[]')!=1:
        raise ValueError('Unexpected original spec shape; refuse an unverified patch')
    hook=ROOT/'docs/dev/releases/frozen_runtime_hook.py'
    text=text.replace('runtime_hooks=[]','runtime_hooks=['+repr(str(hook))+']')
    if not baseline:
        text=text.replace(needle,"EXE(pyz, a.scripts, [('X utf8', None, 'OPTION')], exclude_binaries=True")
    ast.parse(text)
    path.write_text(text,encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',action='store_true')
    configure(baseline=p.parse_args().baseline)
