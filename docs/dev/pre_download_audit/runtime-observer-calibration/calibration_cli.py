"""A CLI calibration uses real unchanged unittest assertion methods directly."""
from dataclasses import dataclass
from test_observer_contract import ObserverCalibrationTests
@dataclass
class LocalRecord:
    value:int=1
assert LocalRecord().value==1
case=ObserverCalibrationTests('test_property_evaluated_once_and_identity_preserved')
case.test_property_evaluated_once_and_identity_preserved()
