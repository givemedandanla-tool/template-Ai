"""Small stdlib-only Actions support, bounded free-cache budget and timings."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time

from release_cache import ROOT, cache_key, load_locks, write


def budget(used, required, public):
    # Do not raise account/repository limits. Reserve below the included 10GiB
    # default, with 2GiB headroom; unknown usage means no new remote cache save.
    return bool(public and type(used) is int and 0 <= used <= 8*1024**3 and required <= 2*1024**3)


def preflight(output):
    wheels, assets = load_locks()
    required = sum(row['bytes'] for row in wheels['wheels'])+sum(assets[key]['bytes'] for key in ('engine_archive','sources'))
    used, public, error = None, False, None
    try:
        def api(path):
            result = subprocess.run(['gh','api',path],cwd=ROOT,capture_output=True,text=True,timeout=30,check=True)
            return json.loads(result.stdout)
        public = api('repos/givemedandanla-tool/template-Ai')['private'] is False
        used = api('repos/givemedandanla-tool/template-Ai/actions/cache/usage')['active_caches_size_in_bytes']
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as failure:
        error = type(failure).__name__
    result = dict(cache_key=cache_key(), required_bytes=required, existing_cache_bytes=used,
                  public_repository=public, save_allowed=budget(used,required,public),
                  usage_error_type=error, no_budget_or_billing_settings_changed=True)
    write(output,result)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as stream:
            stream.write('key='+result['cache_key']+'\n')
            stream.write('save_allowed='+str(result['save_allowed']).lower()+'\n')
    return result


def external(name, phase, status):
    folder=ROOT/'artifacts'
    marker=folder/(name+'-start.json')
    if phase=='start':
        write(marker,dict(perf_counter=time.perf_counter(),utc=datetime.now(timezone.utc).isoformat()))
        return
    start=json.loads(marker.read_text())
    report=folder/'cache-transfer-timings.json'
    rows=json.loads(report.read_text()) if report.exists() else []
    rows.append(dict(name=name,status=status,seconds=time.perf_counter()-start['perf_counter']))
    write(report,rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['preflight','start','finish'])
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/cache-budget.json')
    parser.add_argument('--name')
    parser.add_argument('--status',default='PASS')
    args=parser.parse_args()
    if args.command=='preflight':print(json.dumps(preflight(args.output)))
    else:external(args.name,args.command,args.status)
