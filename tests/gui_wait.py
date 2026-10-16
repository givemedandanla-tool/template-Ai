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
