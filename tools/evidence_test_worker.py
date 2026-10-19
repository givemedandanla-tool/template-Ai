"""One owned unittest module; raw completion journal survives native crashes."""
import argparse,faulthandler,io,json,os,re,signal,sys,traceback,unittest
from pathlib import Path
from dev_common import ROOT,write_json


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--expected',type=Path,required=True);parser.add_argument('--test-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    expected=json.loads(args.expected.read_text());assert isinstance(expected,list) and 1<=len(expected)<=2000 and len(expected)==len(set(expected))
    if any(not isinstance(x,str) or not re.fullmatch(r'test_[A-Za-z0-9_]+(?:\.[A-Za-z_][A-Za-z0-9_]*){2,}',x) for x in expected):raise ValueError('Only exact existing unittest IDs are allowed')
    if len({x.split('.')[0] for x in expected})!=1:raise ValueError('One module per owned test process')
    sys.path[:0]=[str(ROOT),str(args.test_root.resolve())];os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from run_evidence import EvidenceResult
    log=io.StringIO();errors=[];old=sys.excepthook;result=None
    def hook(kind,value,tb):
        errors.append(dict(type=kind.__name__,message=str(value),traceback=''.join(traceback.format_exception(kind,value,tb))))
        old(kind,value,tb)
    stacks=(args.output/'stacks.log').open('w',encoding='utf-8');sys.excepthook=hook
    faulthandler.enable(file=stacks,all_threads=True)
    # Do not interrupt valid long work with a periodic interpreter stack walk.
    # Fatal faults still dump; the owner requests a stack on an actual deadline.
    stack_signal=getattr(signal,'SIGUSR1',None) if os.name=='posix' else None
    if stack_signal is not None:faulthandler.register(stack_signal,file=stacks,all_threads=True)
    try:
        if os.name=='posix':
            import resource
            resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        # Monolithic discovery previously initialized a shared QApplication via
        # GUI fixture imports. Preserve that contract in every fresh interpreter.
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication([])
        runner=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=lambda *values:EvidenceResult(*values,progress_path=args.output/'progress.json'))
        result=runner.run(unittest.defaultTestLoader.loadTestsFromNames(expected))
        if any(name.startswith('PySide6.') for name in sys.modules):
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QCoreApplication,QEvent
            if QApplication.instance():
                QApplication.instance().processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    except BaseException as error:
        errors.append(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
    finally:
        sys.excepthook=old
        if stack_signal is not None:faulthandler.unregister(stack_signal)
        faulthandler.disable();stacks.close()
        records=list(result.records.values()) if result else []
        write_json(args.output/'results.json',dict(records=records,runtime_errors=errors))
        (args.output/'unittest.log').write_text(log.getvalue(),encoding='utf-8')
    return 0 if result and result.wasSuccessful() and not errors else 1


if __name__=='__main__':raise SystemExit(main())
