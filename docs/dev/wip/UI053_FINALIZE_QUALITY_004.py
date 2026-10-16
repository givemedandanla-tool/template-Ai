"""Finalize only the actual immutable quality004 run; never execute old helpers."""
import json,hashlib,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path('tools').resolve()))
from dev_common import manifest,manifest_digest,contract_digest,write_json
D=Path('docs/dev');F=Path('docs/evidence/runs/RUN-REMAINING28-QUALITY-004');rid='UI-053';ref=str(F/'run.json')
def read(p):return json.loads(p.read_text())
run=read(F/'run.json')
assert run['status']=='PASS' and run['test_count']==940 and run['passed']==940
records=read(F/'tests.json');assert len(records)==940 and all(r['status']=='PASS' for r in records)
assert run['source_unchanged'] and run['capture_exit_code']==0 and run['unhandled_runtime_errors']==0
assert manifest_digest(manifest(code_only=True))==run['source_manifest_sha256']
parent_audit=read(F/'remaining28-full-parent-audit.json');assert parent_audit['verified_count']==7 and not parent_audit['all_28_complete']
claims=read(F/'claims.json');state=read(D/'STATE.json');registry=read(D/'REQUIREMENTS.json');ids=state['pending_revalidation_ids'];assert len(set(ids))==145 and rid in ids
for row in registry['requirements']:
 if row['id'] not in ids:continue
 actual=[c for c in claims if c['requirement_id']==row['id']]
 assert len(actual)==len(row['acceptance']) and actual and all(c['status']=='PASS' and c['contract_sha256']==contract_digest(row) for c in actual),row['id']
media={}
for name,item in run['attachments'].items():
 path=F/name;assert path.stat().st_size==item['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],name
 if path.suffix.lower() in ('.png','.jpg','.jpeg','.pdf'):media[name]=item
archive=Path('.checkpoints/formal-media')/run['id'];assert not archive.exists()
for row in registry['requirements']:
 if row['id'] not in ids:continue
 row.setdefault('first_completion_evidence',ref if row['id']==rid else row.get('evidence_run'))
 row.update(completed=True,status='VERIFIED',review_level='SELF_VERIFIED',evidence_run=ref)
 if row['id']==rid:row['first_full_completion_evidence']=ref;row['next_step']='原9完整軟體SELF；實際凍結引擎/模型/規則/OCR、九域/群組不確定性、反洩漏A/B、原稿對照/完整來源分母、明確決策/撤回/共通隔離。Linux合成/currenthost，非真實準確率/原生Illustrator/Windows參考硬體或獨立覆核。下一UI054。'
write_json(D/'REQUIREMENTS.json',registry)
publication=read(D/'FULL70_PUBLICATION.json');publication['runs'][run['id']]=dict(source_commit=run['source_commit'],attachments=media);write_json(D/'FULL70_PUBLICATION.json',publication)
archive.mkdir(parents=True)
for name in media:shutil.move(str(F/name),str(archive/name))
local=len(media);texts=len(run['attachments'])-local;done=['UI-046','UI-047','UI-049','UI-050','UI-051','UI-052',rid]
contract=read(D/'FIXED70_REMAINING28_CONTRACT.json')
for item in contract['acceptance']:
 if item['parent'] in done:item.update(status='SELF_VERIFIED',evidence_run=ref,source_commit=run['source_commit'])
contract.update(verified_parent_count=7,remaining_parent_count=21);write_json(D/'FIXED70_REMAINING28_CONTRACT.json',contract)
audit=read(D/'REMAINING28_CLAUSE_AUDIT.json')
for item in audit['parents']:
 assert item['id'] in done
 item.update(status='SELF_VERIFIED_SOFTWARE',evidence_run=ref,source_commit=run['source_commit'])
assert sum(len(p['clauses']) for p in audit['parents'])==71;write_json(D/'REMAINING28_CLAUSE_AUDIT.json',audit)
for name in ('FULL70_PROGRESS.json','FULL_70_COMPLETION_PLAN.json'):
 value=read(D/name)
 for item in value['rows']:
  if item['id']==rid:item.update(state='CLOSED_FULL_SOFTWARE_SELF_VERIFIED',first_completion_evidence=ref)
  if item['state']=='CLOSED_FULL_SOFTWARE_SELF_VERIFIED':item['evidence']=ref
 if name=='FULL70_PROGRESS.json':value.update(closed=49,remaining=21,latest_evidence=ref)
 else:value.update(closed_parent_count=49,remaining_parent_count=21,latest_evidence_run=ref,next_package='UI054-ROOT-CAUSE-REPAIR-EXACT11')
 write_json(D/name,value)
heading='剩餘28已完成UI046/UI047/UI049/UI050/UI051/UI052/UI053七題，共71原條款；940/940正式PASS、0skip/0Qt錯誤、capture0、source unchanged。全75：51 VERIFIED／21 PARTIAL／3 DEFERRED；固定70：49閉合／21仍部分。CORE87／GOV7另計。'
road=read(D/'PROJECT_ROADMAP.json')
for item in road['topics']:
 if item['id']==rid:item.update(current_status='VERIFIED',review_level='SELF_VERIFIED',registered_acceptance_reference='docs/dev/REQUIREMENTS.json#'+rid,next_step='原9完整軟體SELF；actualsource-only推論/九域/反洩漏/公平A-B/原稿診斷/批准撤回/重大隔離。Linux合成與host測量，不宣稱真實準確率/nativeAI/Windows參考實機/獨立覆核。下一UI054。')
 if item['current_status']=='VERIFIED':item['software_evidence']=ref
road.update(current_parent_counts=dict(VERIFIED=51,PARTIAL=21,DEFERRED=3),latest_status_note=heading);write_json(D/'PROJECT_ROADMAP.json',road)
lines=['# 全75父題狀態與接續順序','',heading,'','下一UI054根因／受控局部修復／獨立再驗收／安全回退。無新增父題；UI048最後、UI056D/REV03延後，無EXE/多代理/main合併。','','|順序組|原父題|名稱|狀態|下一步／證據|','|---|---|---|---|---|']
for item in sorted(road['topics'],key=lambda i:(i['order_group'],i['id'])):lines.append('|'+ '|'.join(str(v).replace('|','／').replace('\n',' ') for v in (item['order_group'],item['id'],item['title'],item['current_status'],item['next_step']))+'|')
(D/'PROJECT_ROADMAP.md').write_text('\n'.join(lines)+'\n')
lines=['# 固定70進度','',heading,'','|原父題|狀態|證據|','|---|---|---|']
for item in read(D/'FULL70_PROGRESS.json')['rows']:lines.append('|'+item['id']+'|'+item['state']+'|'+str(item.get('evidence',''))+'|')
(D/'FULL70_PROGRESS.md').write_text('\n'.join(lines)+'\n')
p=D/'PARTIAL_70_GAP_REPORT.md';v=p.read_text();p.write_text('> 正文保留4238ebc固定70歷史缺口；最新[FULL70_PROGRESS](FULL70_PROGRESS.md)：49完整軟體條款SELF／21仍部分。本輪剩餘28完成七題，原前輪28保留。\n'+v[v.index('\n'):])
p=D/'PROJECT_GOAL.md';p.write_text('> 最新續行（2026-10-16）：'+heading+' 下一UI054；以下保留歷史里程碑。\n\n'+p.read_text())
state.update(active_task='REMAINING28-UI053-COMPLETE-NEXT-UI054',current_work='UI053 actual940PASS/71originalclauses;7of28; preparing required publication checkpoint and Gate, then UI054',latest_evidence_run=ref,pending_revalidation_ids=[],next_work_package='UI054-ROOT-CAUSE-REPAIR-EXACT11',latest_progress_snapshot='docs/dev/progress/PROGRESS-20261016-REMAINING28-QUALITY.json',planned_evidence_run=None)
state['last_formal_validation']=dict(run=ref,source_commit=run['source_commit'],tests=940,passed=940,skipped=0,unhandled_runtime_errors=0,capture_exit_code=0,source_unchanged=True,registered_parent_clauses=71,parent_count=7,attachments=len(run['attachments']),text_metadata=texts,local_media=local)
state['remaining28_result']=dict(target=28,completed=7,remaining=21,new_original_parents=0,revised_original_parents=7,completed_original_parent_ids=done,parent_counts=dict(verified=51,partial=21,deferred=3),core_verified=87,governance_verified=7)
state['publication_status']=dict(run=run['id'],text_metadata_remote_verified=False,publication_scope_gate='PENDING_ACTUAL_CHECK',local_media_count=local,strict_all_attachment_publication=False)
write_json(D/'STATE.json',state)
write_json(D/'REMAINING28_QUALITY_VERIFICATION.json',dict(status='PASS_MILESTONE_7_OF_28',goal_complete=False,target_parents=28,verified_this_turn=7,remaining=21,verified_parent_ids=done,source_commit=run['source_commit'],evidence_run=ref,full_original_clauses=71,tests=940,passed=940,skipped=0,unhandled_runtime_errors=0,capture_exit_code=0,source_unchanged=True,requirements_revalidated=145,text_metadata=texts,media_local_only=local,windows_verified=False,reference_hardware_verified=False,native_illustrator_accuracy_certified=False,independent_review=False))
p=D/'WORK_LOG.md';p.write_text(p.read_text()+'\n### UI053 full original9 formal self-verification milestone\n- '+heading+'\n- Source '+run['source_commit']+';145requirement claimdigests exact;'+str(texts)+' text metadata/'+str(local)+' localmedia retained under exact FULL70_PUBLICATION hashes. Publication Gate must actuallyPASS afterremotecheckpoint beforepublicationclaim.\n- Originalintegrated152/3ERROR fixturelog retained; fixedLogo7PASS andthisactualfull940PASS supersede only softwarefailure, no historicalrecordoverwritten. No realproductioncalibration/nativeAI/Windowshardware/independentreview claimed. NextUI05411originalclauses; do notstop at7of28.\n')
print(json.dumps(dict(status='PASS_MILESTONE_7_OF_28',source=run['source_commit'],text_metadata=texts,local_media=local,requirements=145)))
