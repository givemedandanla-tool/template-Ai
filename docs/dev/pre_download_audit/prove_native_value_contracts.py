"""Minimal native type contracts, authored small values, no private assets."""
import json,hashlib,os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np,scipy
from scipy.ndimage import distance_transform_edt
from PySide6 import __version__ as qt_version
from PySide6.QtCore import QByteArray,QRect,qInstallMessageHandler,qWarning
from PySide6.QtWidgets import QApplication,QStyleOptionViewItem,QDialog
app=QApplication.instance() or QApplication([])
assert bytes(QByteArray(b'authored stderr'))==b'authored stderr'
option=QStyleOptionViewItem();option.rect=QRect(1,2,30,40);copy=QStyleOptionViewItem(option);copy.rect=option.rect.adjusted(0,0,0,-18);assert copy.rect==QRect(1,2,30,22) and option.rect.height()==40
a=np.array([[True,False],[False,False]]);b=np.array([[False,True],[False,False]]);left=distance_transform_edt(~a);right=distance_transform_edt(~b);assert isinstance(left,np.ndarray) and isinstance(right,np.ndarray);assert (left[b].mean()+right[a].mean())/(2*a.shape[0])==.5
F=Path(__file__).resolve().parent;ROOT=F.parents[2];rows=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];dest=F/'native-value-contract-proof.json';proof=json.loads(dest.read_text()).get('proof',{}) if dest.exists() else {};count=0
import sys
sys.path.insert(0,str(ROOT))
from template_ai.recovery_dialog import RecoveryDialog
for member in ['catalog_complete']:
 assert not any(member in base.__dict__ for base in RecoveryDialog.__mro__)
 setters=[base for base in RecoveryDialog.__mro__ if '__setattr__' in base.__dict__]
 assert all(base.__module__.startswith(('PySide6','shiboken6','Shiboken','builtins')) for base in setters)
 dialog=QDialog();setattr(dialog,member,True);assert getattr(dialog,member) is True;dialog.deleteLater()
for kind in [ValueError,Exception]:
 error=kind('Authored calibration');error.recovery_report={'status':'UNKNOWN'};assert error.recovery_report=={'status':'UNKNOWN'}
notes={'D-APP-02058':'Pinned native QStyleOptionViewItem copy has a writable QRect rect; adjusting the copy changes its native rectangle and preserves the original. The static descriptor declaration omits this inherited value field.', 'D-APP-03448':'QProcess.readAllStandardError returns QByteArray. Native QByteArray implements the buffer protocol accepted by bytes, as the independent authored-byte roundtrip proves. Only bounded owned-process stderr is retained by the original code.', 'D-APP-03449':'QProcess.readAllStandardError returns QByteArray. Native QByteArray implements the buffer protocol accepted by bytes, as the independent authored-byte roundtrip proves. Only bounded owned-process stderr is retained by the original code.', 'D-APP-04105':'SciPy distance_transform_edt with omitted output arrays and default return_distances=True/return_indices=False returns ndarray. Its multi-return annotation includes None for the separate caller-supplied-output mode. The exact defaults used by shape_error are checked with a hand-calculated 2x2 distance case.', 'D-APP-04106':'SciPy distance_transform_edt with omitted output arrays and default return_distances=True/return_indices=False returns ndarray. Its multi-return annotation includes None for the separate caller-supplied-output mode. The exact defaults used by shape_error are checked with a hand-calculated 2x2 distance case.'}
from pypdf.generic import RectangleObject
box=RectangleObject([0,0,90*72/25.4,54*72/25.4]);assert abs(float(box.width)*25.4/72-90)<1e-9
received=[]
def first_handler(kind,context,message):received.append(type(context).__name__)
def second_handler(kind,context,message):pass
previous=qInstallMessageHandler(first_handler)
try:
 returned=qInstallMessageHandler(second_handler);assert returned is first_handler and callable(returned)
 qInstallMessageHandler(returned);qWarning('Authored native callback calibration');assert len(received)==1
finally:qInstallMessageHandler(previous)
notes.update({'D-APP-02695':'qInstallMessageHandler returns the previously installed Python callable or None. The actual two-handler roundtrip returns the identical prior callable, invokes it through native Qt logging and restores the original handler. old is checked non-null before forwarding; the object stub lacks the callback signature.', 'D-APP-02742':'Pinned pypdf RectangleObject accepts numeric coordinate sequences and normalizes them to PDF numeric objects. The independent 90x54mm literal coordinate case roundtrips width to90mm within1e-9. The element annotation is narrower than the constructor normalization; no print quality qualification.', 'D-APP-01888':'The immediately constructed ValueError supports its Python instance dictionary, including the new recovery_report metadata name. This does not shadow any builtin exception property. The static builtin exception annotation omits this application report DTO.', 'D-APP-03346':'Actual background witness is builtins.ValueError (test_local_recovery owned-module receipt). Standard ValueError supports the recovery_report Python data member, independently calibrated on owned exceptions. The broad caught Exception annotation does not declare the existing report DTO; arbitrary future custom exceptions are not certified.', 'D-APP-03349':'Exact RecoveryDialog MRO has no native/property catalog_complete collision and no custom __setattr__. Its initialized QDialog supports the inherited Python data namespace; assigning this bool progress flag is valid. This is missing class-field typing, not proof this file-picker branch was exercised.', 'D-APP-03351':'Exact RecoveryDialog MRO has no native/property catalog_complete collision and no custom __setattr__. Its initialized QDialog supports the inherited Python data namespace; assigning this bool progress flag is valid. This is missing class-field typing, not proof this file-picker branch was exercised.'})
for r in rows:
 if r['status']!='UNREVIEWED' or r['id'] not in notes:continue
 key=r['id'];reason=notes[key];proof[key]=dict(original=r['original'],reason=reason,versions=dict(pyside=qt_version,scipy=scipy.__version__,numpy=np.__version__),source_sha256=hashlib.sha256((ROOT/r['original']['path']).read_bytes()).hexdigest(),demonstration='bytes(QByteArray), QStyleOptionViewItem native QRect copy/set and 2x2 exact chamfer=.5 all PASS',scope='Only these pinned native signatures, not font identity, arbitrary inputs or native Windows qualification');r.update(status='TYPE_CONTRACT_GAP' if key in ['D-APP-01888','D-APP-03346','D-APP-03349','D-APP-03351'] else 'TOOL_LIMITATION',severity='P2_NATIVE_MULTI_RETURN_OR_DESCRIPTOR_STUB',affected_workflow=r['original']['path'],root_cause_or_blocker=reason,evidence=['native-value-contract-proof.json#'+key],repro_command_and_result='.venv/bin/python docs/dev/pre_download_audit/prove_native_value_contracts.py: all authored minimal native assertions PASS',regression_and_result='Actual product tests retained separately; this is type signature calibration',remaining_condition='Windows/private corpus/physical print still deferred');count+=1
(F/'diagnostic-ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));dest.write_text(json.dumps(dict(method=__doc__,proof=proof),ensure_ascii=False,indent=2)+'\n');print('native value signatures',count)
