"""One-use UI054 finalization, only after immutable REPAIR003 truly succeeds."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path('tools').resolve()))
from dev_common import manifest,manifest_digest,contract_digest,write_json
from dev_governance import render
D=Path('docs/dev');F=Path('docs/evidence/runs/RUN-REMAINING28-REPAIR-003');rid='UI-054';ref=str(F/'run.json')
def read(path):return json.loads(path.read_text())
run=read(F/'run.json');records=read(F/'tests.json')
assert Path('docs/qa/targeted/remaining28-repair-003-parent-exit.txt').read_text().strip()=='0'
assert run['status']=='PASS' and run['test_count']==1001 and run['passed']==1001
assert len(records)==1001 and len({r['id'] for r in records})==1001 and all(r['status']=='PASS' for r in records)
assert run['source_unchanged'] and run['capture_exit_code']==0 and run['unhandled_runtime_errors']==0
assert run['planned_test_count']==1001 and run['not_completed_test_count']==0
modules=read(F/'test-modules.json');assert modules['completed_tests']==1001
assert all(m.get('exit_code')==0 for m in modules['modules'])
assert manifest_digest(manifest(code_only=True))==run['source_manifest_sha256']
parent_audit=read(F/'remaining28-full-parent-audit.json');assert parent_audit['verified_count']==8 and not parent_audit['all_28_complete']
claims=read(F/'claims.json');state=read(D/'STATE.json');registry=read(D/'REQUIREMENTS.json');ids=state['pending_revalidation_ids'];assert len(set(ids))==146 and rid in ids
for row in registry['requirements']:
 if row['id'] not in ids:continue
 actual=[c for c in claims if c['requirement_id']==row['id']]
 assert len(actual)==len(row['acceptance']) and actual and all(c['status']=='PASS' and c['contract_sha256']==contract_digest(row) for c in actual),row['id']
for name,item in run['attachments'].items():
 path=F/name;assert path.stat().st_size==item['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],name
row=next(r for r in registry['requirements'] if r['id']==rid);assert len(row['acceptance'])==11 and row['full_acceptance_registered']
contract=read(D/'FIXED70_REMAINING28_CONTRACT.json');entry=next(x for x in contract['acceptance'] if x['parent']==rid);assert entry['clause_count']==11
limits=['Authored synthetic legal local sources on current Linux host; no real production accuracy calibration or native Illustrator corpus certification','No Windows/16GB/RTX5050/VivoBook or independent review claim','Explicit source/truth/impact approval remains required; unknown dependencies stay unknown','No automatic source/facts/customer/template rewriting, no holdout training promotion, no prepress approval']
implementation=['template_ai/quality_repairs.py','template_ai/quality_repair_training.py','template_ai/quality_repair_rules.py','template_ai/quality_repair_truth.py','template_ai/quality_repair_gates.py','template_ai/quality_repair_releases.py','template_ai/quality_repair_commands.py','template_ai/quality_repair_dialog.py','template_ai/quality_rule_selector.py']
audit=read(D/'REMAINING28_CLAUSE_AUDIT.json');assert rid not in [x['id'] for x in audit['parents']]
plan=read(D/'UI054_EXECUTION_PLAN.json')
audit['parents'].append(dict(id=rid,source_clauses_sha256=plan.get('original_parent_sha256',plan.get('source_clauses_sha256')),implementation=implementation,clauses=row['acceptance'],status='SELF_VERIFIED_SOFTWARE',limits=limits,evidence_run=ref,source_commit=run['source_commit']))
assert audit['parents'][-1]['source_clauses_sha256']=='13e2c0f1dee610fa6485a53f806bef1dadacd9f0c920a32953851121af942498'
audit['unregistered_parent_ids'].remove(rid);assert len(audit['unregistered_parent_ids'])==20
for item in audit['parents']:item.update(evidence_run=ref,source_commit=run['source_commit'])
assert sum(len(p['clauses']) for p in audit['parents'])==82;write_json(D/'REMAINING28_CLAUSE_AUDIT.json',audit)
for row in registry['requirements']:
 if row['id'] not in ids:continue
 row.setdefault('first_completion_evidence',ref if row['id']==rid else row.get('evidence_run'))
 row.update(completed=True,status='VERIFIED',review_level='SELF_VERIFIED',evidence_run=ref)
 if row['id']==rid:row['first_full_completion_evidence']=ref;row['next_step']='原11完整軟體SELF；真來源問題/根因/隔離候選/順序三Gate/顯式部署回退與七頁GUI。Linux合成/currenthost，非生產準確率/nativeAI/Windows參考硬體或獨立覆核。下一UI055。'
write_json(D/'REQUIREMENTS.json',registry)
done=[p['id'] for p in audit['parents']]
for item in contract['acceptance']:
 if item['parent'] in done:item.update(status='SELF_VERIFIED',evidence_run=ref,source_commit=run['source_commit'])
contract.update(verified_parent_count=8,remaining_parent_count=20);write_json(D/'FIXED70_REMAINING28_CONTRACT.json',contract)
for name in ('FULL70_PROGRESS.json','FULL_70_COMPLETION_PLAN.json'):
 value=read(D/name)
 for item in value['rows']:
  if item['id']==rid:item.update(state='CLOSED_FULL_SOFTWARE_SELF_VERIFIED',first_completion_evidence=ref)
  if item['state']=='CLOSED_FULL_SOFTWARE_SELF_VERIFIED':item['evidence']=ref
 if name=='FULL70_PROGRESS.json':value.update(closed=50,remaining=20,latest_evidence=ref)
 else:value.update(closed_parent_count=50,remaining_parent_count=20,latest_evidence_run=ref,next_package='UI055-EXACT11-TRUSTED-SAMPLE-POOL')
 write_json(D/name,value)
heading='剩餘28已完成UI046/UI047/UI049/UI050/UI051/UI052/UI053/UI054八題，共82原條款；1001/1001正式PASS、0skip/0Qt錯誤、capture0、source unchanged。全75：52 VERIFIED／20 PARTIAL／3 DEFERRED；固定70：50閉合／20仍部分。CORE87／GOV7另計。'
road=read(D/'PROJECT_ROADMAP.json')
for item in road['topics']:
 if item['id']==rid:item.update(current_status='VERIFIED',review_level='SELF_VERIFIED',registered_acceptance_reference='docs/dev/REQUIREMENTS.json#'+rid,next_step='原11完整軟體SELF；可重現順序修復/再驗收/顯式部署回退與七頁GUI。Linux合成/currenthost，不宣稱真實準確率/nativeAI/Windows參考實機/獨立覆核。下一UI055。')
 if item['current_status']=='VERIFIED':item['software_evidence']=ref
road.update(current_parent_counts=dict(VERIFIED=52,PARTIAL=20,DEFERRED=3),latest_status_note=heading);write_json(D/'PROJECT_ROADMAP.json',road)
lines=['# 全75父題狀態與接續順序','',heading,'','下一UI055可信樣本／來源驗證／版本與污染防護；持續剩餘20。','','|順序組|原父題|名稱|狀態|下一步／證據|','|---|---|---|---|---|']
for item in sorted(road['topics'],key=lambda i:(i['order_group'],i['id'])):lines.append('|'+ '|'.join(str(v).replace('|','／').replace('\n',' ') for v in (item['order_group'],item['id'],item['title'],item['current_status'],item['next_step']))+'|')
(D/'PROJECT_ROADMAP.md').write_text('\n'.join(lines)+'\n')
lines=['# 固定70進度','',heading,'','|原父題|狀態|證據|','|---|---|---|']
for item in read(D/'FULL70_PROGRESS.json')['rows']:lines.append('|'+item['id']+'|'+item['state']+'|'+str(item.get('evidence',''))+'|')
(D/'FULL70_PROGRESS.md').write_text('\n'.join(lines)+'\n')
p=D/'PARTIAL_70_GAP_REPORT.md';v=p.read_text();p.write_text('> 正文保留4238ebc固定70歷史缺口；最新[FULL70_PROGRESS](FULL70_PROGRESS.md)：50完整軟體條款SELF／20仍部分。本輪剩餘28完成八題。\n'+v[v.index('\n'):])
p=D/'PROJECT_GOAL.md';p.write_text('> 最新續行（2026-10-16）：'+heading+' 下一UI055；以下保留歷史里程碑。\n\n'+p.read_text())
state.update(active_task='REMAINING28-UI054-COMPLETE-NEXT-UI055',current_work='UI054 actual1001PASS/82originalclauses;8of28; publication checkpoint/Gate then UI055/rest20',latest_evidence_run=ref,pending_revalidation_ids=[],next_work_package='UI055-EXACT11-TRUSTED-SAMPLE-POOL',planned_evidence_run=None,next_step='完成publication Gate後立即UI055/rest20，不停milestone')
state['last_formal_validation']=dict(run=ref,source_commit=run['source_commit'],tests=1001,passed=1001,skipped=0,unhandled_runtime_errors=0,capture_exit_code=0,source_unchanged=True,registered_parent_clauses=82,parent_count=8,attachments=len(run['attachments']),new_run_all_media_published=True)
state['remaining28_result']=dict(target=28,completed=8,remaining=20,new_original_parents=0,revised_original_parents=8,completed_original_parent_ids=done,parent_counts=dict(verified=52,partial=20,deferred=3),core_verified=87,governance_verified=7)
state['publication_status']=dict(run=run['id'],remote_verified=False,publication_scope_gate='PENDING_ACTUAL_CHECK',new_run_all_attachments_published=True,previous_explicit_media_exceptions_unchanged=True)
write_json(D/'STATE.json',state)
write_json(D/'REMAINING28_REPAIR_VERIFICATION.json',dict(status='PASS_MILESTONE_8_OF_28',goal_complete=False,target_parents=28,verified_this_turn=8,remaining=20,verified_parent_ids=done,source_commit=run['source_commit'],evidence_run=ref,full_original_clauses=82,tests=1001,passed=1001,skipped=0,unhandled_runtime_errors=0,capture_exit_code=0,source_unchanged=True,requirements_revalidated=146,attachments=len(run['attachments']),limits=limits))
p=D/'ACTIVE_DEVELOPMENT_HANDOFF.md';p.write_text('# 現行：UI054實際完成8/28；立即UI055及剩餘20\n\n'+heading+'\n\n- 正式run REPAIR003 source '+run['source_commit']+'；實際parent exit0，全部原始附件須正常保存GitHub，新run不增媒體例外。先完成publication checkpoint/native ACK與require-evidence publication-scope Gate。\n- 原REPAIR001/002失敗完整保留；不得覆寫。003實際證明selected回呼與治理索引修復。\n- 下一UI055_EXECUTION_PLAN.json：原11規範、實際LabelStudio1.21.0參考。沿用FACTS/SAMPLE/RULE/DATASET/MODEL，無新DB／新付費服務；完成軟體再處理外部原稿與參考硬體證明。\n- 不停milestone、不合併main、不做EXE、不啟動多代理。\n\n'+p.read_text())
p=D/'WORK_LOG.md';p.write_text(p.read_text()+'\n## UI054 actual REPAIR003 finalization\n\n'+heading+' Source '+run['source_commit']+'; every claim digest and attachment verified, parent shell exit0, immutable source manifest exact. Prior REPAIR001/002 remain failures. New complete run attachments use normal GitHub persistence, no new exception. Next UI055/rest20, goal incomplete.\n')
render();print(json.dumps(dict(status='PASS_MILESTONE_8_OF_28',source=run['source_commit'],attachments=len(run['attachments']),requirements=146)))
