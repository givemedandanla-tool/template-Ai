"""Original actual-EXE acceptance with bounded authored-fixture state diagnostics."""
import argparse
import json
from pathlib import Path
import sys
from contextlib import nullcontext

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools'),str(ROOT/'tests')]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    import windows_release
    from test_automatic_training import AutomaticTrainingTests
    from template_ai.storage import Library
    from template_ai.automatic_training import AutomaticTraining
    original=AutomaticTrainingTests.tearDown
    def observe_then_cleanup(worker):
        try:
            library=Library(worker.library.root)
            try:
                service=AutomaticTraining(library)
                def selected(row):
                    return {key:row[key] for key in ('id','revision','phase','stage','state','error','issues','pause_reasons','reason','items') if key in row}
                value=dict(scope='AUTHORED_RELEASE_FIXTURE_ONLY_NO_PRIVATE_DATA',
                    actual_units=service.store.count('AUTO_UNIT'),
                    jobs=[selected(row) for row in service.store.records('AUTO_JOB')],
                    units=[selected(row) for row in service.store.records('AUTO_UNIT')])
                # The fixture is authored by the original test's setUp. No user
                # library path or alternate data input is accepted by this CLI.
                raw=json.dumps(value,ensure_ascii=False,indent=2)
                if len(raw.encode())>32000:raise ValueError('Synthetic observation exceeds32KiB')
                args.output.mkdir(parents=True,exist_ok=True)
                (args.output/'worker-observation.json').write_text(raw+'\n',encoding='utf-8')
            finally:
                library.close()
        finally:
            original(worker)
    AutomaticTrainingTests.tearDown=observe_then_cleanup
    try:
        native = sys.platform == 'win32' and args.executable.suffix.lower() == '.exe'
        from probe_engine_environment import isolated_host, invalid_cases, installed_case
        with isolated_host(args.executable.absolute()) if native else nullcontext():
            windows_release.exercise(args.executable.absolute(),args.output.resolve())
            if native:
                invalid_cases(args.executable.absolute(),args.output.resolve())
        if native:
            installed_case(args.executable.absolute(),args.output.resolve())
        summary=json.loads((args.output/'summary.json').read_text(encoding='utf-8'))
        if summary['actual_frozen_executable'] and sys.platform=='win32':
            for phase in ['exercise','resume']:
                if 'FROZEN_UTF8_MODE=1' not in (args.output/(phase+'.log')).read_text(encoding='utf-8',errors='replace'):
                    raise RuntimeError('Actual frozen interpreter UTF8 mode was not verified')
            for phase in ['exercise','resume']:
                engine=json.loads((args.output/('bundled-engine-'+phase+'.json')).read_text())
                if engine['status']!='PASS' or not engine['external_override_present']:
                    raise RuntimeError('Actual bundled converter routing was not verified')
            summary['bundled_engine_acceptance']='PASS'
            summary['external_decoy_ignored']=True
            summary['system_installation_absent_during_acceptance']=True
            summary['invalid_engine_scenarios']=2
            windows_release.write(args.output/'summary.json',summary)
    finally:
        AutomaticTrainingTests.tearDown=original

if __name__=='__main__':main()
