"""Observe actual prepared desktop workflows with OS network syscalls.

The localhost negative-control trace is separate from product traces. A missing
observer or unsuccessful test run can never be reported as zero-network PASS.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from dev_common import manifest,manifest_digest


def read_ip_attempts(path):
    lines=path.read_text(errors='replace').splitlines()
    return [line for line in lines if re.search(r'\b(?:connect|sendto|sendmsg)\(',line)
            and re.search(r'\bAF_INET6?\b',line)]


def main():
    folder=ROOT/'docs/dev/non_code_audit/execution-001/offline-observation-001'
    folder.mkdir(exist_ok=False)
    before=manifest_digest(manifest(ROOT,code_only=True));started=time.monotonic()
    if not shutil.which('strace'):
        (folder/'summary.json').write_text(json.dumps(dict(status='BLOCKED_NO_OS_OBSERVER'))+'\n')
        return 2
    # No route/host-network setting is altered: an isolated child namespace is
    # attempted, and lack of kernel support/permission is recorded explicitly.
    isolation=subprocess.run(['unshare','--user','--map-root-user','--net','true'],capture_output=True,text=True)
    (folder/'namespace-capability.txt').write_text(f'EXIT: {isolation.returncode}\n'+isolation.stderr)
    trace=['strace','-f','-qq','-e','trace=network','-s','96','-o']
    observer=folder/'observer-localhost-canary.trace'
    demo=subprocess.run([*trace,str(observer),str(ROOT/'.venv/bin/python'),'-c',
      "import socket;s=socket.socket();s.settimeout(1);s.connect_ex(('127.0.0.1',1));s.close()"],
      cwd=ROOT,capture_output=True,text=True,timeout=15)
    (folder/'observer-control-stderr.txt').write_text(demo.stderr)
    observed=observer.exists() and bool(read_ip_attempts(observer))
    if demo.returncode!=0 or not observed:
        summary=dict(status='BLOCKED_OBSERVER_NOT_VALIDATED',control_exit=demo.returncode,
                     localhost_canary_detected=observed,reason='Cannot interpret an empty/blocked trace as offline evidence.')
        (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return 2
    runtime=folder/'product-desktop.trace'
    command=[str(ROOT/'.venv/bin/python'),'docs/dev/pre_download_audit/run_local_audit.py',
             '--output',str(folder/'desktop-run'),'--module','test_desktop_workspace',
             '--module','test_offline_support','--workers','1']
    if isolation.returncode==0:command=['unshare','--user','--map-root-user','--net',*command]
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen')
    try:
        process=subprocess.run([*trace,str(runtime),*command],cwd=ROOT,env=env,capture_output=True,text=True,timeout=360)
        code=process.returncode;output=process.stdout+process.stderr;timed_out=False
    except subprocess.TimeoutExpired:
        code=None;output='Outer timeout;no complete offline proof.';timed_out=True
    (folder/'command.log').write_text(output)
    run_path=folder/'desktop-run/summary.json'
    result=json.loads(run_path.read_text()) if run_path.is_file() else {}
    attempts=read_ip_attempts(runtime) if runtime.is_file() else None
    good=(code==0 and not timed_out and result.get('software_execution')=='PASS'
          and result.get('runtime_errors')==0 and attempts==[]
          and manifest_digest(manifest(ROOT,code_only=True))==before)
    summary=dict(status='PASS_TESTED_LINUX_SCENARIOS' if good else 'FAIL_OR_INCOMPLETE',
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        code_manifest_sha256=before,source_unchanged=manifest_digest(manifest(ROOT,code_only=True))==before,
        observer_control_detected_localhost_tcp=observed,product_ip_connection_or_datagram_attempts=len(attempts) if attempts is not None else None,
        namespace_isolation='ENABLED' if isolation.returncode==0 else 'UNAVAILABLE_OBSERVATION_ONLY',
        test_command_exit=code,test_summary=result,seconds=time.monotonic()-started,
        trace_sha256=hashlib.sha256(runtime.read_bytes()).hexdigest() if runtime.is_file() else None,
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        qualification='Actual Linux prepared desktop/tested flows only;no Windows/all-code/all-time network guarantee.',
        no_remote_destination_used_by_control=True)
    (folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary));return 0 if good else 1


if __name__=='__main__':raise SystemExit(main())
