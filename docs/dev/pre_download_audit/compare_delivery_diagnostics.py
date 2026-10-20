"""Preserve original occurrence multiset, include runtime-only diagnostics, no baseline mutation."""
import argparse,collections,json,re,hashlib
from pathlib import Path
F=Path(__file__).resolve().parent;ROOT=F.parents[2];p=argparse.ArgumentParser();p.add_argument('--prefix',default='final-delivery');p.add_argument('--output',default='delivery-diagnostic-comparison.json');a=p.parse_args()
original=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()]
renames={'host_window':'window','font_input':'font','size_input':'size','width_input':'width','height_input':'height','style_input':'style','measurement_label':'result','root_layout':'layout','scroll_area':'scroll','output_size_mm':'size','cancel_event':'event'}
def norm(s):
 for new,old in renames.items():s=re.sub(r'\.'+new+r'\b','.'+old,s)
 return re.sub(r'\s+','',s)
def key(f,message=True):return(f['tool'],f['rule'],f['path'],norm(f['context']),*([norm(f['message'])] if message else []))
index=collections.defaultdict(list);source_index=collections.defaultdict(list)
for r in original:index[key(r['original'])].append(r);source_index[key(r['original'],False)].append(r)
profiles=[];union={}
for scope in ('application','tools','tests'):
 for mode in ('standard','runtime-pyright'):
  q=F/f'{a.prefix}-{scope}-{mode}-001/report.json';report=json.loads(q.read_text());counts=collections.Counter();matched=0;pending=0;profile_id=q.parent.name
  for finding in report['findings']:
   if finding['tool']!='pyright':continue
   k=key(finding);counts[k]+=1;ordinal=counts[k];identity=k+(ordinal,)
   entry=union.setdefault(identity,dict(finding=finding,occurrence=ordinal,profiles=[],status='UNREVIEWED',original_ids=[]));entry['profiles'].append(profile_id)
   available=index.get(k,[])
   if len(available)>=ordinal:
    old=available[ordinal-1];entry.update(status='ORIGINAL_REVIEW_LINKED',original_ids=[old['id']],original_disposition=old['status'],evidence=old['evidence']);matched+=1
   else:
    prior=source_index.get(key(finding,False),[])
    if prior:entry['same_source_original_candidates']=[r['id'] for r in prior]
    pending+=1
  profiles.append(dict(profile=profile_id,source=report.get('source'),counts=dict(report.get('counts',{})),pyright_occurrences=sum(counts.values()),exact_original_matched=matched,not_exact_original=pending,coverage=report['coverage'],report_sha256=hashlib.sha256(q.read_bytes()).hexdigest()))
entries=list(union.values());
for i,r in enumerate(entries,1):r['id']=f'DELIVERY-DIAG-{i:05}'
result=dict(method=__doc__,normalization=renames,original_occurrences=len(original),original_unchanged=True,profile_results=profiles,unique_current_occurrences=len(entries),unreviewed=sum(r['status']=='UNREVIEWED' for r in entries),findings=entries)
(F/a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('union',len(entries),'unreviewed',result['unreviewed']);print(collections.Counter(r['finding']['path'] for r in entries if r['status']=='UNREVIEWED'))
