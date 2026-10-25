"""Check the exact native font suite; preserve font names locally only."""
import ctypes as C,json,os
from pathlib import Path
P=C.c_void_p;I=C.c_int32;B=C.c_ubyte
def inspect_fonts(lib,ctx,out,emit,has_text=True):
 basic=(P*8).from_address(ctx);acquire=C.CFUNCTYPE(I,C.c_char_p,I,C.POINTER(P))(basic[0]);release=C.CFUNCTYPE(I,C.c_char_p,I)(basic[1])
 suite=P();error=acquire(b'AI Font Suite',6,C.byref(suite))
 if error or not suite.value:raise RuntimeError('Native font check unavailable')
 def fn(index,*args):return C.CFUNCTYPE(I,*args)((P*(index+1)).from_address(suite.value)[index])
 rows=[]
 try:
  count=I();error=fn(0,P)(C.byref(count))
  if error or not 0<=count.value<10000:raise RuntimeError('Invalid native font count')
  for index in range(count.value):
   key=P();error=fn(1,I,P)(index,C.byref(key))
   if error:raise RuntimeError('Font list query failed')
   name=C.create_string_buffer(1024);substituted=B()
   if fn(19,P,P,C.c_int16)(key,name,1024):raise RuntimeError('Font name query failed')
   if fn(28,P,P)(key,C.byref(substituted)):raise RuntimeError('Font substitution check failed')
   aliases=[]
   for slot in (11,18,21):
    alias=C.create_string_buffer(1024)
    if not fn(slot,P,P,C.c_int16)(key,alias,1024):
     try:value=alias.value.decode('utf8')
     except UnicodeDecodeError:value=alias.value.decode('mbcs','replace')
     aliases.append(value)
   rows.append({'postscript_name':name.value.decode('utf8','replace'),'substituted':bool(substituted.value),'aliases':aliases})
  missing=[row['postscript_name'] for row in rows if row['substituted']]
  declared=json.loads(os.environ.get('REVIEW_SOURCE_FONT_FAMILIES','[]'))
  available={name.casefold().strip() for row in rows if not row['substituted'] for name in [row['postscript_name'],*row['aliases']]}
  missing=sorted(set(missing+[name for name in declared if name.casefold().strip() not in available]))
  result={'count':count.value,'substituted_count':len(missing),'missing':missing,'fonts':rows,'source_declared_families':declared,'document_has_text':has_text,'status':'PASS' if not missing else ('MISSING_FONTS' if has_text else 'UNUSED_DEFAULT_FONT_REFERENCE')}
  (Path(out)/'native-fonts.local.json').write_text(json.dumps(result,indent=2),encoding='utf8')
  emit('native_font_check',count=count.value,substituted_count=len(missing))
  if missing and has_text:raise RuntimeError('Native font substitution detected')
  return result
 finally:release(b'AI Font Suite',6)
