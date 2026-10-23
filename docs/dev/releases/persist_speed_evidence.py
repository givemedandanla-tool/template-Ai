"""Publish bounded synthetic validation evidence, never product Releases/assets."""
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]
BRANCH='release-speed-evidence/v1'
REMOTE='https://github.com/givemedandanla-tool/template-Ai.git'


def git(folder,*args):
    return subprocess.check_output(['git','-C',str(folder),*args],stderr=subprocess.PIPE,timeout=120).decode().strip()


def main(phase='final'):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('Authorized runner only')
    source=git(ROOT,'rev-parse','HEAD')
    job=os.environ['RELEASE_SPEED_JOB']
    if job not in {'native','warm','guards'}:raise ValueError('Unknown job')
    run=os.environ['GITHUB_RUN_ID'];attempt=os.environ.get('GITHUB_RUN_ATTEMPT','1')
    if not run.isdecimal() or not attempt.isdecimal():raise ValueError('Invalid run identity')
    artifacts=ROOT/'artifacts'
    timing=artifacts/'release-timings.json'
    status=json.loads(timing.read_text())['status'] if timing.exists() else 'FAILED_BEFORE_PIPELINE'
    if job=='guards' and (artifacts/'admin-tests.json').exists():
        status='ADMIN_GUARDS_PASS_NOT_PRODUCT_BUILD' if json.loads((artifacts/'admin-tests.json').read_text())['status']=='PASS' else 'FAILED_NOT_VERIFIED'
    if phase=='start':status='RUNNING'
    if os.environ.get('RELEASE_SPEED_JOB_RESULT')=='failure':status='FAILED_NOT_VERIFIED'
    report=dict(source_commit=source,status=status,job=job,run_id=run,attempt=attempt,
                run_url='https://github.com/givemedandanla-tool/template-Ai/actions/runs/'+run,
                path=source+'/'+run+'-'+attempt+'/'+(job+'-start' if phase=='start' else job),recorded_utc=datetime.now(timezone.utc).isoformat(),
                scope='SYNTHETIC_RELEASE_TOOL_VALIDATION_NOT_PRIVATE_CORPUS_OR_USER_HARDWARE')
    with tempfile.TemporaryDirectory(prefix='speed-evidence-') as raw:
        folder=Path(raw)
        git(folder,'init');git(folder,'config','user.name','github-actions[bot]')
        git(folder,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        git(folder,'remote','add','origin',REMOTE)
        if git(folder,'ls-remote','--heads','origin',BRANCH):
            git(folder,'fetch','--depth=1','origin',BRANCH);git(folder,'checkout','-b','evidence','FETCH_HEAD')
        else:git(folder,'checkout','--orphan','evidence')
        target=folder/report['path']
        target.mkdir(parents=True,exist_ok=False)
        allowed=['release-timings.json','cache-transfer-timings.json','cache-inputs.json','cache-local-warm.json','cache-prebuild.json',
                 'cache-budget.json','release-impact-plan.json','release-manifest.json','SHA256SUMS.txt',
                 'corresponding-source-verification.json','governance-gate.json','installed-dependencies.txt',
                 'admin-tests.json',
                 'WINDOWS_RUNTIME.txt','download/download-verification.json',
                 'download-draft/download-verification.json','download-public/download-verification.json',
                 'source-tests/summary.json','source-tests/tests.json','source-tests/catalog.json','source-tests/runtime-errors.json']
        selected=[artifacts/name for name in allowed]
        for pattern in ('*.log','package-check/*.json','package-check/*.log','package-check/*.png'):
            selected+=list(artifacts.glob(pattern))
        for path in sorted(set(selected)):
            if path.is_file() and not path.is_symlink() and path.stat().st_size<=8*1024**2:
                dest=target/path.relative_to(artifacts);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        for path in (target/'status.json',folder/'latest.json'):
            path.write_text(json.dumps(report,indent=2)+'\n')
        git(folder,'add','.');git(folder,'commit','-m','Preserve release speed '+job+' '+run+' attempt '+attempt)
        git(folder,'push','origin','HEAD:refs/heads/'+BRANCH)
    print(json.dumps(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['start','final'],default='final')
    main(parser.parse_args().phase)
