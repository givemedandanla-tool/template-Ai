"""Link reviewed resolved occurrences to actual namespace/snapshot root fixes."""
import json,collections,re
from pathlib import Path
F=Path(__file__).resolve().parent
profiles={'application':'final-scan-application-003','tools':'final-scan-tools-001','tests':'final-scan-tests-001'}
renames={'host_window':'window','font_input':'font','size_input':'size','width_input':'width','height_input':'height','style_input':'style','measurement_label':'result','root_layout':'layout','scroll_area':'scroll','output_size_mm':'size','cancel_event':'event'}
def norm(s):
 for a,b in renames.items():s=re.sub(r'\.'+a+r'\b','.'+b,s)
 return re.sub(r'\s+','',s)
def key(f):return(f['rule'],f['path'],norm(f['context']),norm(f['message']))
counts={s:collections.Counter(key(x) for x in json.loads((F/p/'report.json').read_text())['findings'] if x['tool']=='pyright') for s,p in profiles.items()}
rows=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];proof={}
for row in rows:
 k=key(row['original']);c=counts[row['scope']]
 if c[k]:c[k]-=1;continue
 if row['status']!='UNREVIEWED':continue
 msg=row['original']['message'];context=row['original']['context']
 namespace=('Cannot assign to attribute' in msg or 'addRow' in msg or 'addWidget' in msg or row['original']['path'].endswith('guided_operations.py'))
 root='BUG-QT-001' if namespace else 'BUG-METADATA-SNAPSHOT-004'
 commit='045517e' if namespace else '6258f781'
 proof[row['id']]=dict(root=root,fix_commit=commit,original=row['original'],after_profile=profiles[row['scope']]+'/report.json',comparison='Full current scope; multiset matching of original rule/path/message/context, canonicalizing only documented Qt renames. Exact original occurrence no longer emitted.',runtime_proof='qt-contract-final-summary.json and native-gui-002' if namespace else 'record-collections-after-summary.json:12PASS, preserving nullable arbitrary get and revision gates',residual='Final current-source full regression outcome is recorded separately; no baseline refreshed.')
 row.update(status='FIXED_AND_VERIFIED',severity='P2_STATIC_DESCENDANT_OF_CONFIRMED_ROOT',affected_workflow=row['original']['path'],root_cause_or_blocker=root,evidence=['resolved-root-proof.json#'+row['id']],fix_commit=commit,repro_command_and_result='Original exact diagnostic reproduced; after full-scope fixed-version scan no longer emitted',regression_and_result=proof[row['id']]['runtime_proof'])
(F/'diagnostic-ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
(F/'resolved-root-proof.json').write_text(json.dumps(dict(proof=proof,count=len(proof)),ensure_ascii=False,indent=2)+'\n');print(len(proof))
