"""Make exact scenario/test links; do not equate names with exhaustive coverage."""
import ast,hashlib,json,re
from pathlib import Path
F=Path(__file__).resolve().parent;ROOT=F.parents[2];catalog=json.loads((F/'full-regression-005/catalog.json').read_text())
groups=[
 ('ownership','人物／公司／共享／Logo 不錯綁',r'(ownership|cross_owner|shared|entity_relations|logo.*bind|stable.*identit|same.*string)'),
 ('input_limits','長字串、多筆、尺寸、未知與無解不截短',r'(long|truncate|capacity|overlong|unsolv|unknown|limit|dimension)'),
 ('versions','來源／模型／草稿／定稿的版次與確認競態',r'(stale|revision|confirm.*race|version|accepted.*artifact|pinned|overwrite)'),
 ('learning','分割封存、語意、學習區域與確定性',r'(holdout|leak|joint|semantic|determin|assignment|default_order|repeat|equival)'),
 ('lifetime','取消、關閉、舊回呼、暫停、重啟與恢復',r'(cancel|close|restart|resume|pause|callback_lifetime)'),
 ('faults','損壞、竄改、衝突、原子保存與回復',r'(corrupt|tamper|atomic|rollback|conflict|wrong_password|failed.*write|snapshot)'),
 ('offline_privacy','離線、敏感資訊、報告範圍與路徑',r'(offline|privacy|redact|sensitive|private|network|safe.*report|local_path)'),
 ('artifacts','預覽確認、輸出、備份與報告一致性',r'(preview|confirm|export|output|backup|diagnostic|support)')]
cache={};out=[]
for key,title,pattern in groups:
 ids=[t for t in catalog if re.search(pattern,t,re.I)]
 if not ids:raise RuntimeError('Empty hazard group '+key)
 scenarios=[]
 for identity in ids:
  parts=identity.split('.');p=ROOT/'tests'/(parts[0]+'.py')
  if p not in cache:cache[p]=ast.parse(p.read_text())
  methods=[n for n in ast.walk(cache[p]) if isinstance(n,ast.FunctionDef) and n.name==parts[-1]]
  assertions=[]
  for m in methods:
   for n in ast.walk(m):
    if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('assert'):assertions.append(ast.unparse(n)[:240])
  scenarios.append(dict(id=identity,source=str(p.relative_to(ROOT)),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),assertion_examples=assertions[:4],runtime_status='FINAL_FULL005_PENDING'))
 out.append(dict(hazard=key,title=title,selection='Explicit scenario-name candidates; assertion examples attached. Tests can cover multiple hazards. Neither regex nor total count establishes untested branch coverage.',scenarios=scenarios))
(F/'fault-recovery-matrix.json').write_text(json.dumps(dict(groups=out,scope='All existing catalog names considered, actual test definitions/selected assertions retained',final_result_binding='Pending exact full005 results; root7 test/fix results must be added separately',external_unverified=['Windows実機','私人Illustrator作品／字型與真實學習品質','印刷成品精度','實機效能'],not_claimed='Exhaustive inputs, all operating-system failures or arbitrary database modification. No product acceptance counter is increased.'),ensure_ascii=False,indent=2)+'\n')
print({g['hazard']:len(g['scenarios']) for g in out})
