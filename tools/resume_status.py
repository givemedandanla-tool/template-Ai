"""Bounded, read-only cross-conversation entry. Never dump whole registries or logs."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def status(requirement=None):
    state=json.loads((ROOT/'docs/dev/STATE.json').read_text())
    contract=json.loads((ROOT/state['active_contract']).read_text())
    head=subprocess.run(['git','-C',str(ROOT),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    changes=subprocess.run(['git','-C',str(ROOT),'status','--porcelain'],capture_output=True,text=True,check=True).stdout.splitlines()
    result=dict(repository=state['repository'],branch=state['working_branch'],head=head,
        working_tree_changes=len(changes),active_task=state['active_task'],contract=state['active_contract'],
        target_parents=contract.get('target_parent_ids'),last_confirmed_commit=state['last_confirmed_commit'],
        checkpoint=state['last_confirmed_checkpoint'],latest_evidence=state.get('latest_evidence_run'),
        next_tasks=state.get('next_tasks',[])[:3],pending_remote=state.get('pending_remote',[]),
        read_next=['docs/dev/CONTEXT_AND_PERSISTENCE_RULES.md','docs/dev/ACTIVE_DEVELOPMENT_HANDOFF.md'])
    if requirement:
        registry=json.loads((ROOT/'docs/dev/REQUIREMENTS.json').read_text())
        row=next((r for r in registry['requirements'] if r['id']==requirement),None)
        if row is None:raise ValueError('要求ID不存在')
        result['requirement']={k:row.get(k) for k in ('id','title','status','completed','next_step','evidence_run')}
        result['requirement']['acceptance_count']=len(row['acceptance'])
        result['requirement']['original_clauses_in_contract']=requirement in contract.get('original_clauses',{})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--requirement')
    print(json.dumps(status(parser.parse_args().requirement),ensure_ascii=False,indent=2))
