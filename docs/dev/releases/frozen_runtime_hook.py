"""Report interpreter mode only in authored GitHub release acceptance runs."""
import os
import sys

if os.environ.get('GITHUB_ACTIONS')=='true':
    print('FROZEN_UTF8_MODE='+str(sys.flags.utf8_mode),file=sys.stderr,flush=True)
    import faulthandler
    faulthandler.enable(file=sys.stderr,all_threads=True)
    if sys.platform=='win32' and getattr(sys,'frozen',False):
        # The C watchdog crashed this actual frozen Windows interpreter at
        # exactly 45s (0xc0000005); an earlier exit had the same timing. Keep
        # the same diagnostic threshold using referenced frames under the GIL.
        # The acceptance parent's independent 240s deadline is unchanged.
        import threading
        timer=[None]
        def cancel_safe_traceback():
            if timer[0] is not None:
                timer[0].cancel()
                timer[0]=None
        def safe_traceback_later(timeout,repeat=False,file=None,exit=False):
            if repeat or exit:
                raise ValueError('Authored acceptance uses a single non-exiting diagnostic dump')
            cancel_safe_traceback()
            stream=file if file is not None else sys.stderr
            def dump_referenced_frames():
                print('SAFE_FROZEN_TRACEBACK after '+str(timeout)+'s',file=stream,flush=True)
                frames=sys._current_frames()
                for thread_id,frame in list(frames.items())[:16]:
                    print('Thread '+str(thread_id),file=stream,flush=True)
                    for _ in range(64):
                        if frame is None:break
                        code=frame.f_code
                        name=code.co_filename.rsplit('/',1)[-1].rsplit('\\',1)[-1]
                        print('  '+name+':'+str(frame.f_lineno)+' '+code.co_name,file=stream,flush=True)
                        frame=frame.f_back
            timer[0]=threading.Timer(timeout,dump_referenced_frames)
            timer[0].daemon=True
            timer[0].start()
        faulthandler.dump_traceback_later=safe_traceback_later
        faulthandler.cancel_dump_traceback_later=cancel_safe_traceback
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
