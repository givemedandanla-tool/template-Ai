"""Deterministic load for workflow tests; real sampling/pressure has separate tests.

Synthetic free capacity is never evidence of performance on reference hardware.
"""
import time
from template_ai.runtime_resources import ResourceSnapshot


def controlled_resources(window):
    class Monitor:
        def __init__(self):self.sequence=0
        def snapshot(self):
            self.sequence+=1
            return ResourceSnapshot(time.monotonic(),self.sequence,8*1024**3,6*1024**3,5,4,4*1024**3,64*1024**2,())
        def close(self):pass
    window.runtime.monitor.close();window.runtime.monitor=Monitor();window.runtime.ready_after=0
    window.runtime.gui_lag=lambda:0
