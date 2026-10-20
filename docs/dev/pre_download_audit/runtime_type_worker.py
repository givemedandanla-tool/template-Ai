"""Run the original isolated unittest worker with bounded type-only observation.

No payload values, property getters, extra model/API calls or product edits.
"""
import argparse,ast,collections,inspect,json,os,runpy,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools'),str(ROOT/'tests')]
MISSING=object()


def resolve(node,frame):
    if isinstance(node,ast.Name):return frame.f_locals.get(node.id,frame.f_globals.get(node.id,MISSING))
    if isinstance(node,ast.Constant):return node.value
    if isinstance(node,ast.Attribute):
        obj=resolve(node.value,frame)
        if obj is MISSING or obj is None:return MISSING
        try:fields=object.__getattribute__(obj,'__dict__')
        except (AttributeError,TypeError):fields={}
        if type(fields) is dict and node.attr in fields:return fields[node.attr]
        try:descriptor=inspect.getattr_static(obj,node.attr)
        except AttributeError:return MISSING
        if isinstance(descriptor,(property,)) or type(descriptor).__name__=='cached_property':return MISSING
        if isinstance(descriptor,(types.FunctionType,types.BuiltinFunctionType,types.MethodDescriptorType,types.WrapperDescriptorType,staticmethod,classmethod)):
            try:return object.__getattribute__(obj,node.attr)
            except (AttributeError,RuntimeError,TypeError):return MISSING
        return MISSING
    if isinstance(node,ast.Subscript):
        obj=resolve(node.value,frame)
        key=resolve(node.slice,frame) if isinstance(node.slice,(ast.Constant,ast.Name)) else MISSING
        if type(obj) not in (dict,list,tuple,str,bytes) or type(key) not in (str,int):return MISSING
        try:return obj[key]
        except (KeyError,IndexError,TypeError):return MISSING
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='get' and 1<=len(node.args)<=2 and not node.keywords:
        obj=resolve(node.func.value,frame)
        if type(obj) is dict and isinstance(node.args[0],ast.Constant) and type(node.args[0].value) in (str,int):
            default=resolve(node.args[1],frame) if len(node.args)>1 else None
            if default is MISSING:return MISSING
            return obj.get(node.args[0].value,default)
    return MISSING


def typename(value):
    cls=type(value)
    return cls.__module__+'.'+cls.__qualname__


class Observer:
    def __init__(self,points):
        self.by_file={};self.by_code={};self.rows={};self.active=None;self.errors=collections.Counter();self.positions={};self.accepted=0;self.local_codes=set()
        for p in points:
            path=str((ROOT/p['path']).resolve());self.by_file.setdefault(path,{}).setdefault(p['line'],[]).append(p)
            p['_targets']=[(t['label'],ast.parse(t['expression'],mode='eval').body) for t in p['targets']]
            self.rows[p['id']]={'visits':0,'values':{},'returns':{},'normal_calls':{},'raised_calls':{},'test_contexts':[],'member_checks':{}}
        self.pending={}
        self.monitor=sys.monitoring;self.tool=None
        for candidate in (5,4,3):
            try:self.monitor.use_tool_id(candidate,'template-ai-type-audit');self.tool=candidate;break
            except ValueError:continue
        if self.tool is None:raise RuntimeError('No free native monitoring tool slot')

    def frame(self,code):
        current=sys._getframe(1)
        while current is not None and current.f_code is not code:current=current.f_back
        return current

    def context(self,row):
        if self.active and self.active not in row['test_contexts'] and len(row['test_contexts'])<8:row['test_contexts'].append(self.active)

    def start(self,code,offset):
        try:
            path=code.co_filename
            if path in self.by_file:
                self.by_code[code]=self.by_file[path]
                self.monitor.set_local_events(self.tool,code,self.monitor.events.LINE|self.monitor.events.PY_RETURN|self.monitor.events.CALL)
                self.local_codes.add(code)
            elif path.startswith(str(ROOT/'template_ai')+os.sep):
                self.monitor.set_local_events(self.tool,code,self.monitor.events.PY_RETURN)
                self.local_codes.add(code)
            if code.co_name=='run' and 'unittest' in path and path.endswith('case.py'):
                f=self.frame(code);obj=f.f_locals.get('self') if f else None
                if obj is not None:
                    method=object.__getattribute__(obj,'_testMethodName');cls=type(obj);self.active=cls.__module__+'.'+cls.__qualname__+'.'+method
                return None
        except BaseException as error:self.errors['START_'+type(error).__name__]+=1
        return self.monitor.DISABLE

    def sample(self,f,points,phase):
        for p in points:
            row=self.rows[p['id']]
            if row['visits']>=128:continue
            row['visits']+=1;self.context(row)
            phases=row.setdefault('sample_phases',{});phases[phase]=phases.get(phase,0)+1
            for label,node in p['_targets']:
                obj=resolve(node,f)
                key='UNAVAILABLE_WITHOUT_EXECUTING_USER_CODE' if obj is MISSING else typename(obj)
                values=row['values'].setdefault(label,{})
                values[key]=values.get(key,0)+1
                by_phase=row.setdefault('values_by_phase',{}).setdefault(phase,{}).setdefault(label,{})
                by_phase[key]=by_phase.get(key,0)+1
                if obj is not MISSING and p.get('member') and label=='receiver':
                    try:inspect.getattr_static(obj,p['member']);exists=True
                    except AttributeError:exists=False
                    state=typename(obj)+':'+str(exists);row['member_checks'][state]=row['member_checks'].get(state,0)+1
                    by_phase=row.setdefault('member_checks_by_phase',{}).setdefault(phase,{})
                    by_phase[state]=by_phase.get(state,0)+1

    def line(self,code,line):
        try:
            f=self.frame(code)
            if f is None:self.errors['FRAME_MISSING']+=1;return
            previous=self.pending.pop(id(f),None)
            if previous is not None:self.sample(f,previous,'AFTER_PREVIOUS_LINE')
            points=self.by_code.get(code,{}).get(line)
            if not points:return
            self.sample(f,points,'BEFORE_LINE');self.pending[id(f)]=points
        except BaseException as error:self.errors['LINE_'+type(error).__name__]+=1

    def unwind(self,code,offset,error):
        f=self.frame(code)
        if f is not None:self.pending.pop(id(f),None)

    def call(self,code,offset,func,arg):
        points=self.by_code.get(code)
        if not points:return self.monitor.DISABLE
        f=self.frame(code)
        if f is None:return self.monitor.DISABLE
        position=self.position(code,offset)
        if position is None or position[0] is None:return
        actual=[position[0],position[2],position[1],position[3]]
        for p in points.get(f.f_lineno,[]):
            if actual not in p['call_ranges'] or not p.get('member'):continue
            if not isinstance(func,(types.MethodType,types.BuiltinFunctionType,types.BuiltinMethodType)):continue
            receiver=object.__getattribute__(func,'__self__')
            name=object.__getattribute__(func,'__name__')
            if receiver is None or name!=p['member']:continue
            row=self.rows[p['id']];kind=typename(receiver)
            bucket=row['values'].setdefault('receiver',{});bucket[kind]=bucket.get(kind,0)+1
            state=kind+':True';row['member_checks'][state]=row['member_checks'].get(state,0)+1
            bucket=row.setdefault('member_checks_by_phase',{}).setdefault('EXACT_BOUND_METHOD_CALL',{});bucket[state]=bucket.get(state,0)+1
            self.context(row)

    def position(self,code,offset):
        if code not in self.positions:self.positions[code]=list(code.co_positions())
        rows=self.positions[code];return rows[offset//2] if offset//2<len(rows) else None

    def c_result(self,code,offset,func,arg,raised=False):
        try:
            points=self.by_code.get(code)
            if not points:return
            f=self.frame(code)
            if f is None:return
            position=self.position(code,offset)
            if position is None or position[0] is None:return
            actual=[position[0],position[2],position[1],position[3]]
            for p in points.get(f.f_lineno,[]):
                if actual not in p['call_ranges']:continue
                row=self.rows[p['id']];field='raised_calls' if raised else 'normal_calls';key='NATIVE_CALL_EXACT_SOURCE_RANGE'
                if sum(row[field].values())<128:row[field][key]=row[field].get(key,0)+1;self.context(row)
        except BaseException as error:self.errors['C_RETURN_'+type(error).__name__]+=1

    def returned(self,code,offset,value):
        try:
            f=self.frame(code)
            previous=self.pending.pop(id(f),None) if f is not None else None
            if previous is not None:self.sample(f,previous,'NORMAL_RETURN_AFTER_LINE')
            # Exceptional unwinds are not normal None returns.
            import dis
            if dis.opname[code.co_code[offset]] not in ('RETURN_VALUE','RETURN_CONST'):return
            f=self.frame(code);caller=f.f_back if f else None
            if caller is None:return
            points=self.by_file.get(caller.f_code.co_filename,{}).get(caller.f_lineno,[])
            for p in points:
                if code.co_name not in p['producer_names']:continue
                row=self.rows[p['id']];key=code.co_qualname+':'+typename(value)
                for label,target in p['_targets']:
                    if label=='container' and isinstance(target,ast.Call) and ast.unparse(target.func).split('.')[-1]==code.co_name:
                        bucket=row['values'].setdefault('container_return',{});kind=typename(value);bucket[kind]=bucket.get(kind,0)+1
                if sum(row['returns'].values())<128:row['returns'][key]=row['returns'].get(key,0)+1;self.context(row)
        except BaseException as error:self.errors['PY_RETURN_'+type(error).__name__]+=1

    def install(self):
        m=self.monitor;t=self.tool
        for e,fn in [(m.events.PY_START,self.start),(m.events.LINE,self.line),(m.events.CALL,self.call),(m.events.C_RETURN,self.c_result),(m.events.C_RAISE,lambda *a:self.c_result(*a,raised=True)),(m.events.PY_RETURN,self.returned),(m.events.PY_UNWIND,self.unwind)]:m.register_callback(t,e,fn)
        m.set_events(t,m.events.PY_START|m.events.CALL|m.events.C_RETURN|m.events.C_RAISE|m.events.PY_UNWIND)

    def finish(self):
        m=self.monitor;m.set_events(self.tool,0)
        for code in self.local_codes:
            m.set_local_events(self.tool,code,0)
        for event in (m.events.PY_START,m.events.LINE,m.events.CALL,m.events.C_RETURN,m.events.C_RAISE,m.events.PY_RETURN,m.events.PY_UNWIND):
            m.register_callback(self.tool,event,None)
        m.free_tool_id(self.tool)
        return {'schema':1,'mode':'TYPE_NAMES_ONLY_NO_PAYLOADS_NO_PROPERTY_GETTERS','bounded_visits_per_point':128,'observer_errors':dict(self.errors),'rows':{k:v for k,v in self.rows.items() if v['visits'] or v['returns'] or v['normal_calls'] or v['raised_calls']}}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--points',type=Path,required=True);parser.add_argument('--type-output',type=Path,required=True)
    args,rest=parser.parse_known_args()
    data=json.loads(args.points.read_text())
    for name,expected in data['source_files'].items():
        import hashlib
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Source changed after runtime point mapping')
    observer=Observer(data['points']);observer.install()
    original=sys.argv;sys.argv=[str(ROOT/'tools/evidence_test_worker.py'),*(rest[1:] if rest[:1]==['--'] else rest)]
    try:runpy.run_path(str(ROOT/'tools/evidence_test_worker.py'),run_name='__main__')
    finally:
        result=observer.finish();args.type_output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');sys.argv=original


if __name__=='__main__':main()
