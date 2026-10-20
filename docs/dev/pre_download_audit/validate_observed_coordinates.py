"""Reject runtime proof whose recorded container belongs to an inner index."""
import ast,json,re
from pathlib import Path
F=Path(__file__).resolve().parent;O=Path('/tmp/template-ai-audit-original-373b6ee')
ledger=F/'diagnostic-ledger.jsonl';rows=[json.loads(x) for x in ledger.read_text().splitlines()];byid={r['id']:r for r in rows};p=F/'observed-contract-proof.json';doc=json.loads(p.read_text());valid={};rejected={};cache={}
def canonical(t):
 for a,b in {'host_window':'window','width_input':'width','height_input':'height','size_input':'size','font_input':'font','output_size_mm':'size'}.items():t=re.sub(r'\.'+a+r'\b','.'+b,t)
 return re.sub(r'\s+','',t)
for key,proof in doc['proof'].items():
 row=byid[key]
 if proof['kind']=='REAL_RECEIVER_MEMBER':valid[key]=proof;continue
 path=row['original']['path']
 if path not in cache:
  text=(O/path).read_text();cache[path]=(text.splitlines(),ast.parse(text))
 lines,tree=cache[path];position=row['original_range'];begin=tuple(position['start'][k] for k in ['line','character']);end=tuple(position['end'][k] for k in ['line','character'])
 def coord(n,which):
  ln=getattr(n,'lineno' if which=='start' else 'end_lineno');col=getattr(n,'col_offset' if which=='start' else 'end_col_offset');return(ln-1,len(lines[ln-1].encode()[:col].decode().encode('utf-16-le'))//2)
 def exact(n):return coord(n,'start')==begin and coord(n,'end')==end
 subs=[n for n in ast.walk(tree) if isinstance(n,ast.Subscript)]
 candidates=([n for n in subs if exact(n.value)] if row['rule'] in ['reportOptionalSubscript','reportIndexIssue'] else [n for n in subs if exact(n) or exact(n.slice)])
 targets=[v['expression'] for v in proof['expression']['targets'] if v['label']=='container']
 okay=len(candidates)==1 and targets==[ast.unparse(candidates[0].value)]
 if not okay and len(candidates)==1 and len(targets)==1:okay=canonical(targets[0])==canonical(ast.unparse(candidates[0].value))
 if okay:valid[key]=proof
 else:
  rejected[key]=dict(reason='Original exact range does not identify the observed inner container; no runtime safety/contract conclusion admitted',observed=targets,expected=[ast.unparse(n.value) for n in candidates],original_range=position)
  if row['status']=='TYPE_CONTRACT_GAP' and any('observed-contract-proof' in e for e in row.get('evidence',[])):
   row.update(status='UNREVIEWED',severity='NOT_YET_ASSESSED',root_cause_or_blocker='Runtime coordinate proof rejected: nested expression ambiguity; requires exact outer container observation or independent source contract',evidence=['observed-coordinate-rejections.json#'+key])
# Keep the draft evidence and rejection, rather than hiding the checker mistake.
(F/'observed-contract-proof-draft.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
doc['proof']=valid;doc['counts']={kind:sum(v['kind']==kind for v in valid.values()) for kind in ['REAL_CONTAINER_SCHEMA','REAL_RECEIVER_MEMBER','RECORD_STRING_KEY_NOT_SEQUENCE_INDEX']};doc['coordinate_validation']='Exact original object/full-index/key range required; ambiguous inner-container draft observations rejected'
p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n');(F/'observed-coordinate-rejections.json').write_text(json.dumps(rejected,ensure_ascii=False,indent=2)+'\n');ledger.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));print('accepted',len(valid),'rejected',len(rejected))
