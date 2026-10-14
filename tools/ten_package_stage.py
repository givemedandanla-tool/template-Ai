"""TEN package staging: registers actual tests without claiming product completion."""
import argparse
import json
import sys
import unittest
from pathlib import Path
from dev_common import write_json
from dev_governance import render


def stage(number, module, summary):
    root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root)); sys.path.insert(0, str(root/'tests'))
    p = root/'docs/dev/STATE.json'; state = json.loads(p.read_text()); package = state['ten_packages']['packages'][number-1]
    state['previous_evidence_run'] = state.get('latest_evidence_run') or state.get('previous_evidence_run'); state['latest_evidence_run'] = None
    package['status'] = 'IMPLEMENTED_PENDING_FORMAL'; state['product_version'] = '0.1.'+str(14+number)
    state['next_tasks'] = [{'id': package['id'], 'status': 'IN_PROGRESS', 'action': summary}, {'id': 'TEN-NEXT', 'status': 'CONTINUE', 'action': '完成來源對應回歸／保存／下一包，不等待HUMAN；無EXE。'}]; write_json(p, state)
    (root/'template_ai/__init__.py').write_text('"""矩形排版與人工確認幾何學習。"""\n__version__ = "'+state['product_version']+'"\n')
    def flatten(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite): yield from flatten(item)
            else: yield item.id()
    ids = sorted(flatten(unittest.defaultTestLoader.loadTestsFromName(module)))
    if not ids or any('FailedTest' in tid for tid in ids): raise ValueError('具名驗收測試載入失敗')
    p = root/'docs/dev/REQUIREMENTS.json'; registry = json.loads(p.read_text())
    for r in registry['requirements']:
        if r['kind'] != 'topic' and r['completed']: r.update(status='IMPLEMENTED_PENDING_VERIFICATION', completed=False)
        if r['id'] in package['requirements']:
            r.update(status='IMPLEMENTED_PENDING_VERIFICATION', completed=False, next_step='正式來源對應驗收與GitHub保存範圍讀回')
            for criterion in r['acceptance']: criterion['tests'] = ids
    write_json(p, registry); render(root)
    p = root/'docs/dev/WORK_LOG.md'; old = p.read_text(); p.write_text('# 開發工作紀錄\n\n## 十包 '+str(number)+' 可恢復實作\n\n'+summary+'\n\n'+old.removeprefix('# 開發工作紀錄\n'))
    print(json.dumps({'package': number, 'requirements': package['requirements'], 'tests_registered': len(ids)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('number', type=int); parser.add_argument('module'); parser.add_argument('summary'); args = parser.parse_args(); stage(args.number, args.module, args.summary)
