"""Report interpreter mode only in authored GitHub release acceptance runs."""
import os
import sys

if os.environ.get('GITHUB_ACTIONS')=='true':
    print('FROZEN_UTF8_MODE='+str(sys.flags.utf8_mode),file=sys.stderr,flush=True)
    import faulthandler
    faulthandler.enable(file=sys.stderr,all_threads=True)
    if os.environ.get('BUNDLE_DIAGNOSTIC_TRACE')=='true':
        import time
        started=time.monotonic()
        traced={'bundled_runtime','runtime_report','environment_facts','implementation_fingerprint',
                'bundle','build_support_bundle','validate_report','report_summary','_version','_resume_worker'}
        counter=[0]
        def observe(frame,event,arg):
            if event not in {'call','return'} or counter[0]>=400:return
            name=frame.f_code.co_name
            if name not in traced:return
            file=frame.f_code.co_filename.rsplit('/',1)[-1].rsplit('\\',1)[-1]
            if file not in {'inkscape_runtime.py','offline_support.py','release_check.py'}:return
            counter[0]+=1
            print('AUTHORED_TRACE '+event+' '+file+':'+name+' '+str(round(time.monotonic()-started,3)),file=sys.stderr,flush=True)
        sys.setprofile(observe)
