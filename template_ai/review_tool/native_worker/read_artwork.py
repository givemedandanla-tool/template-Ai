"""Version-limited, read-only suite experiment. Never save an input document."""
import ctypes as C,json,hashlib,struct,math
from pathlib import Path
P=C.c_void_p;I=C.c_int32;H=C.c_int16;B=C.c_ubyte
def read_artwork(lib,ctx,source,output,emit,callback=None):
 def check(err,name):
  if err:raise RuntimeError(name+' error '+hex(err&0xffffffff))
 basic=(P*8).from_address(ctx)
 acquire=C.CFUNCTYPE(I,C.c_char_p,I,C.POINTER(P))(basic[0]);release=C.CFUNCTYPE(I,C.c_char_p,I)(basic[1]);held=[]
 def suite(name,versions):
  for v in versions:
   ptr=P();err=acquire(name.encode(),v,C.byref(ptr));emit('suite_acquire',name=name,version=v,error=hex(err&0xffffffff))
   if not err and ptr.value:held.append((name,v));return ptr.value
  raise RuntimeError('Required suite unavailable: '+name)
 def fn(s,index,*args):return C.CFUNCTYPE(I,*args)((P*(index+1)).from_address(s)[index])
 before=hashlib.sha256(source.read_bytes()).hexdigest();opened=P();path=P();us=P();artlist=P();props=P();result={'source':str(source),'sha256_before':before,'bounds_raw_format':'to validate against synthetic geometry'}
 try:
  # These two constructors/destructors are verified in this exact signed CC 2020
  # binary's host-data consumer. Public mirror headers are for a later SDK.
  dllpath=Path(lib._name)
  if hashlib.sha256(dllpath.read_bytes()).hexdigest()!='fb1ded30ca8b3034f91a835ab09ca440d1ab545e193d27897629164d5970d2c2':raise RuntimeError('Unverified AILib build')
  string_new=C.CFUNCTYPE(P,P,C.c_wchar_p)(lib._handle+0x430590);string_delete=C.CFUNCTYPE(None,P)(lib._handle+0xb6f70)
  path_new=C.CFUNCTYPE(P,P,P,B)(lib._handle+0x46af20);path_delete=C.CFUNCTYPE(None,P)(lib._handle+0x46af40)
  arts=suite('AI Art Suite',[20]);boards=suite('AI Artboard Suite',[4]);paths=suite('AI Path Suite',[12]);layers=suite('AI Layer Suite',[13])
  string_new(C.byref(us),str(source));path_new(C.byref(path),C.byref(us),1)
  op=lib.AILOpenDocument;op.argtypes=[P,H,C.POINTER(P)];op.restype=I
  emit('open_begin',input_kind='synthetic' if ('adobe-generated' in source.name or source.name=='synthetic.ai') else 'private-local-only')
  err=op(C.byref(path),2,C.byref(opened));emit('open_returned',error=hex(err&0xffffffff),context_nonnull=bool(opened.value));check(err,'AILOpenDocument')
  if not opened.value:raise RuntimeError('Open returned no document context')
  check(fn(boards,11,P)(C.byref(artlist)),'GetArtboardList');count=I();check(fn(boards,15,P,P)(C.byref(artlist),C.byref(count)),'GetArtboardCount')
  if not 0<count.value<=1000:raise RuntimeError('Unreasonable artboard count')
  result['artboard_count']=count.value;result['artboards']=[]
  check(fn(boards,0,P)(C.byref(props)),'InitArtboardProperties')
  for i in range(count.value):
   check(fn(boards,19,P,I,P)(C.byref(artlist),i,C.byref(props)),'GetArtboardProperties');buf=C.create_string_buffer(64)
   check(fn(boards,3,P,P)(C.byref(props),buf),'GetArtboardPosition')
   result['artboards'].append({'f32':list(struct.unpack('<4f',buf.raw[:16])),'f64':list(struct.unpack('<4d',buf.raw[:32])),'raw':buf.raw.hex()})
  layer=P();check(fn(layers,4,P)(C.byref(layer)),'GetFirstLayer');pending=[];layer_seen=set()
  while layer.value:
   if layer.value in layer_seen or len(layer_seen)>10000:raise RuntimeError('Layer traversal safety bound')
   layer_seen.add(layer.value);root=P();check(fn(arts,4,P,P)(layer,C.byref(root)),'GetFirstArtOfLayer')
   if root.value:pending.append(root.value)
   next_layer=P();check(fn(layers,5,P,P)(layer,C.byref(next_layer)),'GetNextLayer');layer=next_layer
  result['layer_count']=len(layer_seen);seen=set();items=[]
  while pending:
   art=pending.pop()
   if art in seen:continue
   seen.add(art)
   if len(seen)>100000:raise RuntimeError('Art traversal safety bound')
   typ=H();check(fn(arts,6,P,P)(art,C.byref(typ)),'GetArtType');bounds=C.create_string_buffer(64);check(fn(arts,13,P,P)(art,bounds),'GetArtBounds')
   row={'type':typ.value,'bounds_f32':list(struct.unpack('<4f',bounds.raw[:16])),'bounds_f64':list(struct.unpack('<4d',bounds.raw[:32]))}
   if typ.value==2:
    n=H();check(fn(paths,0,P,P)(art,C.byref(n)),'GetPathSegmentCount');closed=C.c_uint32();check(fn(paths,6,P,P)(art,C.byref(closed)),'GetPathClosed');row.update(segment_count=n.value,closed=closed.value)
   items.append(row)
   for index in [10,11]:
    nxt=P();err=fn(arts,index,P,P)(art,C.byref(nxt))
    if not err and nxt.value:pending.append(nxt.value)
  result['art_items']=items;result['path_count']=sum(x['type']==2 for x in items);result['status']='OPEN_AND_INSPECTED';emit('artwork_summary',artboards=count.value,art_items=len(items),paths=result['path_count'])
  if callback is not None:result['export']=callback(result)
 finally:
  if props.value:fn(boards,2,P)(C.byref(props))
  if artlist.value:fn(boards,12,P)(C.byref(artlist))
  if opened.value:
   # The observed function is void: normal return paths do not set EAX.
   close=lib.AILCloseDocument;close.argtypes=[P];close.restype=None;emit('close_begin');close(opened);emit('close_returned')
  if path.value:path_delete(C.byref(path))
  if us.value:string_delete(C.byref(us))
  for name,v in reversed(held):release(name.encode(),v)
  result['sha256_after']=hashlib.sha256(source.read_bytes()).hexdigest();result['source_unchanged']=result['sha256_after']==before
  with output.open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
 return result
