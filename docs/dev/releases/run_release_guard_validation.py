"""Current Windows administrative guards plus measured real-project indexing."""
from pathlib import Path
import subprocess
import sys

from release_impact import make_plan
from release_pipeline import ROOT, Stages


if __name__=='__main__':
    subprocess.run([sys.executable,str(Path(__file__).with_name('run_release_speed_tests.py')),'artifacts'],check=True)
    stages=Stages(ROOT/'artifacts/release-timings.json','administrative_guards_not_product_build')
    try:
        with stages.stage('real_project_batch_git_impact_plan'):
            make_plan('auto',ROOT/'artifacts/release-impact-plan.json',force_build=True)
        stages.data['status']='ADMIN_GUARDS_PASS_NOT_PRODUCT_BUILD'
    except BaseException:
        stages.data['status']='FAILED_NOT_VERIFIED'
        raise
    finally:
        stages.save()
