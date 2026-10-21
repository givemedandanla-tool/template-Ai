"""Actual Windows baseline/fixed comparison; never packages or publishes a release."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools'),str(Path(__file__).parent)]
from configure_frozen_utf8 import configure
from windows_release import make_spec,source_identity

def main():
    if sys.platform!='win32':raise RuntimeError('Native Windows A/B required')
    identity=source_identity();assert identity['source_matches_head']
    output=ROOT/'artifacts/package-check';output.mkdir(parents=True,exist_ok=False)
    attempts=[]
    for mode in ['baseline','utf8']:
        make_spec();configure(baseline=mode=='baseline')
        with (ROOT/'artifacts/pyinstaller.log').open('ab') as log:
            command=[sys.executable,'-m','PyInstaller','--noconfirm','build/release/TemplateAI.spec']
            built=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if built.returncode:raise RuntimeError('PyInstaller failed in '+mode)
        exe=ROOT/'dist/TemplateAI/TemplateAI.exe';exe_sha=hashlib.sha256(exe.read_bytes()).hexdigest()
        folder=ROOT/'artifacts'/('probe-'+mode)
        ran=subprocess.run([sys.executable,str(ROOT/'docs/dev/releases/run_frozen_probe.py'),'--executable',str(exe),'--output',str(folder)],cwd=ROOT)
        for path in folder.iterdir():
            if path.is_file() and path.suffix in {'.json','.log','.png'} and path.stat().st_size<8*1024*1024:
                shutil.copy2(path,output/(mode+'-'+path.name))
        log=(folder/'exercise.log').read_text(encoding='utf-8',errors='replace')
        observation=json.loads((folder/'worker-observation.json').read_text(encoding='utf-8'))
        if mode=='baseline':
            check=json.loads((folder/'packaged-exercise.json').read_text(encoding='utf-8'))
            if not(ran.returncode and 'FROZEN_UTF8_MODE=0' in log and observation['actual_units']==0
                and check.get('failure_check')=='after:frozen_json_pipe_worker'
                and any('來源或衍生快取失效' in str(item.get('error','')) for job in observation['jobs'] for item in job.get('items',[]))):
                raise RuntimeError('Baseline did not reproduce the exact cache/encoding failure; no causal claim')
        else:
            summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
            if not(ran.returncode==0 and summary['status']=='PASS' and summary['actual_frozen_executable']
                and 'FROZEN_UTF8_MODE=1' in log and observation['actual_units']==2
                and exe_sha!=attempts[0]['executable_sha256']):
                raise RuntimeError('UTF8 fixed actual executable did not pass unchanged full acceptance')
        attempts.append(dict(mode=mode,exit_code=ran.returncode,executable_sha256=exe_sha,
            actual_units=observation['actual_units'],runtime_utf8_mode=0 if mode=='baseline' else 1))
    if source_identity()!=identity:raise RuntimeError('Product source changed during A/B')
    (output/'utf8-comparison.json').write_text(json.dumps(dict(status='PASS_DIAGNOSTIC_ONLY_NOT_PUBLISHED',
        source=identity,attempts=attempts,source_tests='NOT_EXECUTED_BY_THIS_DIAGNOSTIC',
        original_frozen_checks_unchanged=True),indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
