"""Callable completion plus deferred error/cancel ownership, compatible with 3-argument job mocks."""
from dataclasses import dataclass
from typing import Callable,Any


@dataclass
class JobCallbacks:
    done:Callable
    error:Callable
    cancel_event:Any=None

    def __call__(self,value):return self.done(value)
