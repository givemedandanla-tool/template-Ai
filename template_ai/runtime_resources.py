"""Measured current-runtime resources and bounded hysteresis; no reference-hardware promise."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import math,os,threading,time

MiB=1024*1024


def _number(value):
    return value if type(value) in (int,float) and math.isfinite(value) and value>=0 else None


def read_cgroup():
    """Known Linux v2 limits only. Unknown applicable limits stay explicit."""
    root=Path('/sys/fs/cgroup')
    if os.name!='posix' or not (root/'cgroup.controllers').exists():return dict(applicable=False)
    result=dict(applicable=True,errors=[])
    try:
        for line in Path('/proc/self/cgroup').read_text()[:32768].splitlines():
            if line.startswith('0::'):
                relative=line[3:].lstrip('/');candidate=(root/relative).resolve()
                if candidate.is_relative_to(root) and (candidate/'memory.max').exists():root=candidate
                break
    except OSError as error:result['errors'].append('container-location:'+type(error).__name__)
    for name,key in [('memory.max','memory_max'),('memory.current','memory_current'),('cpu.max','cpu_max'),('cpu.stat','cpu_stat')]:
        try:result[key]=(root/name).read_text()[:1024].strip()
        except OSError as error:result['errors'].append(key+':'+type(error).__name__)
    return result


@dataclass(frozen=True)
class ResourceSnapshot:
    sampled_at:float
    sequence:int
    memory_total:int|None
    memory_available:int|None
    cpu_percent:float|None
    effective_cpus:float|None
    disk_free:int|None
    process_rss:int|None
    unknown:tuple[str,...]
    basis:str='CURRENT_RUNTIME_ONLY_NOT_REFERENCE_HARDWARE'

    def to_dict(self):return asdict(self)


class ResourceSampler:
    def __init__(self,provider=None,cgroup_reader=read_cgroup,clock=time.monotonic):
        self.provider=provider;self.cgroup_reader=cgroup_reader;self.clock=clock;self.previous=None;self.sequence=0

    def sample(self,data_root):
        now=self.clock();self.sequence+=1;unknown=[];total=available=cpu=cores=disk=rss=None;usage=None
        provider=self.provider
        if provider is None:
            try:import psutil;provider=psutil
            except ImportError:unknown.append('psutil-unavailable')
        if provider is not None:
            try:
                memory=provider.virtual_memory();total=_number(memory.total);available=_number(memory.available)
                if total is None or available is None:unknown.append('memory-invalid')
                elif available>total:available=total
            except Exception as error:unknown.append('memory:'+type(error).__name__)
            try:
                host_cpu=_number(provider.cpu_percent(interval=None));cores=_number(provider.cpu_count(logical=True))
                if self.previous is not None and host_cpu is not None:cpu=min(100.0,host_cpu)
                else:unknown.append('cpu-first-sample')
            except Exception as error:unknown.append('cpu:'+type(error).__name__)
            try:
                process=provider.Process();rss=_number(process.memory_info().rss)
                if hasattr(process,'cpu_affinity'):
                    affinity=process.cpu_affinity()
                    if affinity:cores=min(cores or len(affinity),len(affinity))
            except Exception as error:unknown.append('process:'+type(error).__name__)
            try:disk=_number(provider.disk_usage(str(data_root)).free)
            except Exception as error:unknown.append('disk:'+type(error).__name__)
        try:group=self.cgroup_reader()
        except Exception as error:group=dict(applicable=True,errors=['probe:'+type(error).__name__])
        if not isinstance(group,dict):group=dict(applicable=True,errors=['container-probe-invalid'])
        if group.get('applicable'):
            try:
                raw=group['memory_max']
                if raw!='max':
                    limit=int(raw);current=int(group['memory_current'])
                    if limit<0 or current<0:raise ValueError('negative container memory')
                    total=min(total,limit) if total is not None else limit
                    available=min(available,max(0,limit-current)) if available is not None else None
                if total is not None and available is not None:available=min(available,total)
            except (KeyError,ValueError,TypeError):available=None;unknown.append('container-memory-unknown')
            try:
                quota,period=group['cpu_max'].split();period=int(period)
                if period<=0:raise ValueError('invalid period')
                if quota!='max':
                    cap=int(quota)/period
                    if cap<=0:raise ValueError('invalid quota')
                    cores=min(cores,cap) if cores is not None else cap
                stats=dict(line.split() for line in group['cpu_stat'].splitlines());usage=int(stats['usage_usec'])
                previous=self.previous
                if previous and previous['usage'] is not None and usage>=previous['usage'] and cores and now>previous['time']:
                    measured=(usage-previous['usage'])/1_000_000/(now-previous['time'])/cores*100
                    cpu=max(cpu or 0,min(100.0,measured))
            except (KeyError,ValueError,TypeError):unknown.append('container-cpu-unknown')
            unknown.extend(group.get('errors',[]))
        self.previous=dict(time=now,usage=usage)
        return ResourceSnapshot(now,self.sequence,total,available,cpu,cores,disk,rss,tuple(dict.fromkeys(unknown)))


class ResourceMonitor:
    """One daemon probe thread; an unresponsive volume never blocks the GUI or shutdown."""
    def __init__(self,data_root,sampler=None,interval=.5):
        self.data_root=Path(data_root);self.sampler=sampler or ResourceSampler();self.interval=max(.1,interval);self.stop_event=threading.Event();self.lock=threading.Lock();self.latest=None;self.thread=None

    def start(self):
        if self.thread and self.thread.is_alive():return
        if self.stop_event.is_set():return
        def run():
            while not self.stop_event.is_set():
                try:value=self.sampler.sample(self.data_root)
                except Exception as error:value=ResourceSnapshot(time.monotonic(),getattr(self.sampler,'sequence',0),None,None,None,None,None,None,('probe-failed:'+type(error).__name__,))
                if self.stop_event.is_set():break
                with self.lock:self.latest=value
                if self.stop_event.wait(self.interval):break
        self.thread=threading.Thread(target=run,name='template-ai-resource-probe',daemon=True);self.thread.start()

    def snapshot(self):
        with self.lock:return self.latest

    def close(self):self.stop_event.set()


@dataclass(frozen=True)
class ResourceDecision:
    allowed:bool
    state:str
    reasons:tuple[str,...]
    reserve_memory_bytes:int
    estimated_peak_bytes:int
    measured:dict|None

    def to_dict(self):return asdict(self)


class AdmissionControl:
    """Per-workload hysteresis counts fresh samples, never repeated reads of one sample."""
    PEAKS={'SCAN':8*MiB,'METADATA':16*MiB,'GEOMETRY':96*MiB,'ANALYSIS':256*MiB,'RESTORE':256*MiB,'EXPORT':192*MiB}

    def __init__(self,clock=time.monotonic,recovery_samples=3,max_age=3,cpu_limit=90,gui_lag_limit=.5):
        if type(recovery_samples) is not int or not 1<=recovery_samples<=20 or _number(max_age) is None or not .1<=max_age<=30 or _number(cpu_limit) is None or not 1<=cpu_limit<=100 or _number(gui_lag_limit) is None or not .05<=gui_lag_limit<=10:raise ValueError('資源背壓門檻不合法')
        self.clock=clock;self.recovery_samples=recovery_samples;self.max_age=max_age;self.cpu_limit=cpu_limit;self.gui_lag_limit=gui_lag_limit;self.states={};self.lock=threading.Lock()

    def decide(self,snapshot,kind='ANALYSIS',estimated_peak_bytes=0,estimated_write_bytes=0,gui_lag=0,interactive=False):
        if kind not in self.PEAKS or type(estimated_peak_bytes) is not int or estimated_peak_bytes<0 or type(estimated_write_bytes) is not int or estimated_write_bytes<0:raise ValueError('資源工作類型／預算不合法')
        reasons=[];reserve=64*MiB;peak=max(self.PEAKS[kind],estimated_peak_bytes)
        if snapshot is None:reasons.append('RESOURCE_SAMPLE_PENDING')
        else:
            age=self.clock()-snapshot.sampled_at
            if not math.isfinite(age) or age<0 or age>self.max_age:reasons.append('RESOURCE_SAMPLE_STALE')
            if snapshot.memory_total is not None:reserve=max(64*MiB,min(512*MiB,int(snapshot.memory_total*.1)))
            if snapshot.memory_available is None:reasons.append('AVAILABLE_MEMORY_UNKNOWN')
            elif snapshot.memory_available<reserve+peak:reasons.append('MEMORY_PRESSURE')
            if snapshot.disk_free is None:reasons.append('WRITABLE_VOLUME_SPACE_UNKNOWN')
            elif snapshot.disk_free<max(32*MiB,estimated_write_bytes*2):reasons.append('DISK_HEADROOM_LOW')
            if snapshot.cpu_percent is not None and snapshot.cpu_percent>=self.cpu_limit:reasons.append('CPU_PRESSURE')
        if gui_lag is not None and gui_lag>self.gui_lag_limit:reasons.append('GUI_HEARTBEAT_LATE')
        if interactive:reasons.append('FOREGROUND_INTERACTION_PRIORITY')
        with self.lock:
            state=self.states.setdefault(kind,dict(paused=False,good=0,last=None))
            sequence=snapshot.sequence if snapshot is not None else None
            if reasons:state.update(paused=True,good=0,last=sequence)
            elif state['paused']:
                if sequence!=state['last']:state['good']+=1;state['last']=sequence
                if state['good']<self.recovery_samples:reasons.append('WAITING_STABLE_RECOVERY_SAMPLES')
                else:state.update(paused=False,good=0)
        return ResourceDecision(not reasons,'ALLOW_SINGLE_WORKER' if not reasons else 'PAUSED_RESOURCES',tuple(reasons),reserve,peak,snapshot.to_dict() if snapshot else None)
