"""Register implemented scopes without promoting parents before formal evidence."""
import argparse,json,sys,unittest
from pathlib import Path
from dev_common import write_json
from dev_governance import render

def stage(module,ids):
    root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'tests')]
    def flatten(s):
        for x in s:
            if isinstance(x,unittest.TestSuite):yield from flatten(x)
            else:yield x.id()
    tests=sorted(flatten(unittest.defaultTestLoader.loadTestsFromName(module)))
    if not tests or any('FailedTest' in x for x in tests):raise ValueError('具名測試載入失敗')
    p=root/'docs/dev/REQUIREMENTS.json';r=json.loads(p.read_text())
    for row in r['requirements']:
        if row['kind']!='topic' and row['completed']:row.update(completed=False,status='IMPLEMENTED_PENDING_VERIFICATION')
        if row['id'] in ids:
            row.update(completed=False,status='IMPLEMENTED_PENDING_VERIFICATION',next_step='等待固定來源全回歸／actual Qt及GitHub讀回')
            for a in row['acceptance']:a['tests']=tests
    write_json(p,r)
    p=root/'docs/dev/SEVENTY_PARENTS_CONTRACT.json';c=json.loads(p.read_text())
    for scope in c['scopes']:
        if scope['id'] in ids:scope.update(status='IMPLEMENTED_PENDING_FORMAL',tests=tests)
    write_json(p,c);render(root);print(json.dumps({'scopes':ids,'registered':len(tests)}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('module');p.add_argument('ids',nargs='+');a=p.parse_args();stage(a.module,a.ids)
