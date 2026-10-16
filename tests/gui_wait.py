"""Bounded GUI event pumping for real asynchronous foreground calculation."""
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

def wait_layout(window,seconds=10):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        QApplication.processEvents();QTest.qWait(5)
        dialog=getattr(window,'foreground_layout_session',None)
        if dialog is not None and not dialog.running:return dialog
    raise AssertionError('Owned foreground layout did not finish in bounded wait')


def job_diagnostics(window,kind='ANALYSIS'):
    if window is None:return 'No owned GUI window recorded'
    import faulthandler,sys
    faulthandler.dump_traceback(file=sys.stderr,all_threads=True)
    decision=window.runtime.admit(kind,foreground=True)
    return str(dict(status=window.statusBar().currentMessage(),allowed=decision.allowed,reasons=list(decision.reasons),active_threads=window.pool.activeThreadCount(),waiting_launches=len(window._waiting_launches),owned_jobs=len(window._background_jobs),policy_error=window.runtime.policy_error,library_closed=window.library.closed))


def wait_for_gui(condition,seconds):
    """Run the real Qt event loop so worker imports/I/O can reacquire the GIL.

    QTest.qWait polling in tight Python loops can starve cold worker imports.
    The watchdog preserves the caller's original wall-time budget.
    """
    from PySide6.QtCore import QEventLoop,QTimer,Qt
    if condition():return True
    loop=QEventLoop();poll=QTimer(loop);watchdog=QTimer(loop);watchdog.setSingleShot(True);watchdog.setTimerType(Qt.PreciseTimer);errors=[]
    def check():
        try:
            if condition():loop.quit()
        except BaseException as error:errors.append(error);loop.quit()
    poll.timeout.connect(check);watchdog.timeout.connect(loop.quit);poll.start(10);watchdog.start(max(1,int(seconds*1000)))
    try:loop.exec()
    finally:poll.stop();watchdog.stop()
    if errors:raise errors[0]
    return bool(condition())


def wait_candidate_edits(window,seconds=10):
    def finished():
        manager=getattr(window,'candidate_edit_dispatcher',None)
        return manager is not None and not window.busy and not manager.pending and manager.active is None
    if not wait_for_gui(finished,seconds):raise AssertionError('Owned candidate edit recheck did not complete: '+job_diagnostics(window,'GEOMETRY'))
