"""Rebuild traceability artifacts; a mapping is explicitly NOT a passing audit.

Runtime results are supplied separately by the original isolated executors.
This script cannot manufacture PASS results or update product requirements.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/dev/non_code_audit/execution-001'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


RULES = [
 ('R01','B02','Every displayed field retains stable identity,real owner and explicit users; equal strings do not imply shared identity.','docs/dev/INPUT_LEARNING_INTERFACE_MAP.md','ALL_INPUTS'),
 ('R02','B01','Values and leading zeroes survive; an engineering budget rejects rather than silently truncates.','docs/dev/INPUT_LEARNING_INTERFACE_MAP.md','ALL_INPUTS'),
 ('R03','F03','Logo identity,owner,source,whole proportions and designated physical size remain bound.','docs/dev/INPUT_LEARNING_INTERFACE_MAP.md','ASSETS'),
 ('R04','B04','Measured,declared,estimated,unknown and confirmed source typography remain distinct; defaults are not source truth.','docs/dev/AI_CROSS_WORK_LEARNING_PLAN.md','OBSERVATION_AND_TRAINING'),
 ('R05','C01','Training uses permitted TRAIN groups; lineage is kept across splits; sealed evaluation is not used to fit.','docs/dev/AI_CROSS_WORK_LEARNING_PLAN.md','MODEL_FITTING'),
 ('R06','C02','New learning produces cross-work shared family/rules; isolated observations are not silently one-output-template-per-work.','docs/dev/AI_CROSS_WORK_LEARNING_PLAN.md','NEW_LEARNING_NOT_LEGACY_MANUAL_SAVE'),
 ('R07','C04','Confidence,style qualification and real generalization require evidence; predictions are not human labels.','docs/dev/AI_CROSS_WORK_LEARNING_CONTRACT.json','LEARNING_QUALITY'),
 ('R08','D01','Substitution is conditional on both endpoints,role,owner,label/icon,font,actual data and joint layout; not unrestricted transitivity.','docs/decisions/2026-10-19-CORE-ADAPTATION-SWAPS-AND-DEFAULTS.md','NEW_FAMILY_ASSIGNMENT'),
 ('R09','C03','Qualified positive support defines advice; known negative demands cannot expand it; no global learned hard maximum is invented.','docs/decisions/2026-10-18-QUALIFIED-TRAINING-STYLE-SUITABLE-REGION.md','CAPACITY_ADVICE_NOT_OUTPUT_PERMISSION'),
 ('R10','D03','A move preserves unaffected protected relative relations while approved joint geometry/typography can adapt.','docs/decisions/2026-10-19-CORE-ADAPTATION-SWAPS-AND-DEFAULTS.md','RELATIVE_EDITING'),
 ('R11','D03','Customer intent is relative placement; font size,ScaleX,frame,alignment and distribution are core rules; professional template tools keep their approved scope.','docs/decisions/2026-10-19-CORE-ADAPTATION-SWAPS-AND-DEFAULTS.md','ROLE_SCOPED_CONTROLS'),
 ('R12','D04','All multiple legal choices have a versioned default; compare equal complete contexts,not mutable aliases.','docs/decisions/2026-10-19-CORE-ADAPTATION-SWAPS-AND-DEFAULTS.md','DETERMINISTIC_SELECTION'),
 ('R13','E04','Published templates and confirmed artifacts keep original versions; reordered accepted work reuses exact accepted bytes.','docs/dev/INPUT_LEARNING_INTERFACE_MAP.md','FIXED_AND_ACCEPTED_ARTIFACTS'),
 ('R14','E01','Confirmation belongs to exact current input,result,policy and dependencies; changes invalidate it.','docs/dev/INPUT_LEARNING_INTERFACE_MAP.md','CONFIRM_AND_EXPORT'),
 ('R15','E03','Cancel,resume,retry,undo and late callbacks preserve target identity and explicit transactional scope.','docs/dev/INPUT_LEARNING_INTERFACE_MAP.md','STATE_TRANSITIONS'),
 ('R16','F04','Completed computation or preview is not formal output qualification; all applicable preflight gates remain required.','docs/dev/REQUIREMENTS.json','OUTPUT'),
 ('R17','G03','Prepared desktop workflows run locally; no automatic source upload or required cloud inference.','docs/dev/GUI_OFFLINE_DELIVERY_CONTRACT_20261020.md','PREPARED_DESKTOP_RUNTIME'),
 ('R18','G02','Reports give faithful plain summaries and professional details through a safe allowlist; private data stays local.','docs/dev/GUI_OFFLINE_DELIVERY_CONTRACT_20261020.md','MANUAL_DIAGNOSTIC_EXPORT'),
 ('R19','H02','Only actual source/tree/blob remote readback qualifies REMOTE_VERIFIED; local-only evidence is labeled local.','docs/dev/DEVELOPMENT_PROTOCOL.md','PERSISTENCE'),
 ('R20','H01','Tests,mappings,synthetic scope,real-corpus qualification and physical print are different claims; unknown/skipped are not PASS.','docs/dev/DEVELOPMENT_PROTOCOL.md','ALL_COMPLETION_CLAIMS'),
 ('R21','H04','Core desktop first; no unrequested web,mobile,EXE or redefinition of8AI packages/75parents.','docs/dev/AI_CROSS_WORK_LEARNING_CONTRACT.json','DELIVERY_SCOPE'),
 ('R22','H04','Use included tools and normal Git operations; do not repeat billing-proof gates or enable paid add-ons/trials.','docs/decisions/2026-10-21-INCLUDED-TOOLS-AND-EXECUTION-EFFICIENCY.md','DEVELOPMENT_EXECUTION')
]

# The following is trace-routing, not a model for automatically interpreting
# arbitrary natural-language requirements or declaring their behavior correct.
ROUTES = [
 (r'人物|公司|共享|歸屬|客戶|主檔|重複|合併|語意|欄位種類|前導零',['B01','B02','E04']),
 (r'來源|畫板|作品|匯入|AI|Illustrator|標記|雜訊|OCR',['B03','B04','C01','F03']),
 (r'字型|字體|字級|ScaleX|字寬|tracking|分散|文字框|字距',['B04','D03','F02']),
 (r'學習|訓練|模型|家族|資料集|驗證集|HOLDOUT|適合|容量',['C01','C02','C03','C04']),
 (r'等效|交換|相容|替代|排版|優選|排序|布局|相對|拖動|對齊',['D01','D02','D03','D04']),
 (r'確認|定稿|版本|重訂|輸出|預覽|PDF|印刷|精度|Logo',['E01','E04','F01','F02','F03','F04']),
 (r'取消|續跑|重試|背景|中斷|回復|復原|備份|還原|批次|進度',['E02','E03','G04']),
 (r'介面|面板|導航|模式|操作|提示|對話|引導|報告|錯誤|離線|隱私|效能|配置',['E02','G01','G02','G03']),
 (r'驗收|證據|測試|checkpoint|GitHub|持久|治理|接續|版本',['A04','H01','H02','H03','H04'])
]


def test_sources():
    found={}
    for path in sorted((ROOT/'tests').glob('test_*.py')):
        source=path.read_text();lines=source.splitlines()
        for node in ast.parse(source).body:
            if not isinstance(node,ast.ClassDef):continue
            for fn in node.body:
                if not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) or not fn.name.startswith('test_'):continue
                calls=[n.func.attr for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
                asserts=sorted(set(x for x in calls if x.startswith('assert')))
                text='\n'.join(lines[fn.lineno-1:fn.end_lineno])
                found[f'{path.stem}.{node.name}.{fn.name}']=dict(path=path.relative_to(ROOT).as_posix(),line=fn.lineno,
                    source_sha256=hashlib.sha256(text.encode()).hexdigest(),direct_assertion_kinds=asserts,
                    assurance='ASSERTION_ANCHOR_NOT_AUTOMATIC_SEMANTIC_PROOF')
    return found


def refresh_views():
    """Repair the stale progress mirror; never infer new completion statuses."""
    registry=json.loads((ROOT/'docs/dev/REQUIREMENTS.json').read_text())
    byid={row['id']:row for row in registry['requirements']}
    path=ROOT/'docs/dev/PROJECT_ROADMAP.json'
    old=json.loads(path.read_text())
    history=ROOT/'docs/dev/history';history.mkdir(exist_ok=True)
    for name in ('PROJECT_ROADMAP.json','PROJECT_ROADMAP.md'):
        backup=history/(Path(name).stem+'_PRE_NONCODE_20261021'+Path(name).suffix)
        if not backup.exists():backup.write_bytes((ROOT/'docs/dev'/name).read_bytes())
    old['schema_version']=2
    if 'current_full70_progress' in old:
        old['historical_full70_progress']=old.pop('current_full70_progress')
    for topic in old['topics']:
        row=byid[topic['id']]
        topic['current_status']=row['status']
        topic['registered_acceptance_count']=len(row['acceptance'])
        topic['software_evidence']=row.get('evidence_run')
        topic['current_status_basis']='Current requirement registry;not an independent new acceptance pass.'
        topic['next_step']=row.get('next_step') or row.get('remaining') or 'See registered scope and its current evidence qualification.'
    counts=dict(Counter(t['current_status'] for t in old['topics']))
    old['current_parent_counts']=counts
    old['source_registry_sha256']=sha(ROOT/'docs/dev/REQUIREMENTS.json')
    old['latest_status_note']='Current registry mirror:75parents;counts below. VERIFIED denotes registered scoped software evidence,not Windows/private-corpus/print qualification. Historical fixed70 counts are preserved separately,not current. Formal source evidence reconciliation is tracked in non_code_audit/execution-001.'
    path.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
    text=['# 產品路線與目前登錄狀態','',
          '本頁從REQUIREMENTS.json同步；舊快照已保存history/PROJECT_ROADMAP_PRE_NONCODE_20261021。狀態是登錄的軟體範圍，不代表本次重新驗收或真實作品／Windows／印刷已合格。正式證據與當前執行結果依STATE及non_code_audit/execution-001。','',
          '目前父題：'+json.dumps(counts,ensure_ascii=False)+'；75筆不重編。AI8包／50條的真實資格仍8部分／0完整。','',
          '|階段|父題|內容|登錄狀態|驗收條款數|','|---|---|---|---|---|']
    for t in old['topics']:
        title=t['title'].replace('|','\\|').replace('\n',' ')
        text.append(f"|{t.get('order_group','')}|{t['id']}|{title}|{t['current_status']}|{t['registered_acceptance_count']}|")
    text+=['','歷史fixed70／舊階段數字保留在原快照；目前需求、實作與剩餘範圍以REQUIREMENTS逐條登錄為準。不要用歷史規劃中的「0實作」覆蓋後續軟體結果，也不要把合成自我驗證提升為完整真實資格。','']
    (ROOT/'docs/dev/PROJECT_ROADMAP.md').write_text('\n'.join(text))
    goal=ROOT/'docs/dev/PROJECT_GOAL.md';body=goal.read_text()
    banner='> **目前狀態入口（2026-10-21非代碼審核修正）**'
    if not body.startswith(banner):
        goal.write_text(banner+'：本檔以下有帶日期的歷史訪談／規劃數字，不能當目前完成狀態。目標定義保留；最新執行／資格見STATE、REQUIREMENTS與PROJECT_ROADMAP。軟體合成驗證與真實學習／Windows／印刷資格分開，原AI8包／50條真實資格8部分／0完整不變。\n\n'+body)
    write('roadmap-view-reconciliation.json',dict(status='RECONCILED_REGISTRY_MIRROR_NOT_NEW_PRODUCT_PASS',
          parent_count=len(old['topics']),current_parent_counts=counts,
          source_registry_sha256=old['source_registry_sha256'],
          all_topic_statuses_equal_registry=all(t['current_status']==byid[t['id']]['status'] for t in old['topics']),
          original_snapshots_preserved=True,product_and_ai_counts_redefined=False))


def build():
    refresh_views()
    plan=json.loads((ROOT/'docs/dev/non_code_audit/PLAN.json').read_text())
    declared={c['id'] for d in plan['domains'] for c in d['checks']}
    rules=[]
    for identity,topic,meaning,path,scope in RULES:
        assert (ROOT/path).is_file() and 'NCA-'+topic in declared
        rules.append(dict(id=identity,audit_topic='NCA-'+topic,normative_meaning=meaning,
                          source=path,source_sha256=sha(ROOT/path),scope=scope,
                          precedence='Latest explicit user decision within matching scope;do not flatten history.'))
    resolutions=[
      dict(id='SCOPE-01',question='UI042 versus UI043',resolution='UI_DECISIONS line644 explicitly withdraws only designed/purchased/purchase-proof categories;customer master,resume and exact dedup authorization remain. No global UI042 replacement.',evidence='docs/UI_DECISIONS.md:644',result='SCOPE_RESOLVED_NOT_PRODUCT_DEFECT'),
      dict(id='SCOPE-02',question='Fixed point size versus joint adaptive rules',resolution='Existing published/confirmed versions retain original rules. New learned instances follow later joint-adaptation decision. Not one global override.',evidence='docs/decisions/2026-10-19-CORE-ADAPTATION-SWAPS-AND-DEFAULTS.md',result='SCOPE_RESOLVED'),
      dict(id='SCOPE-03',question='Customer controls versus professional template editing',resolution='Withdrawn customer font/width/single-double-row controls do not revoke approved professional template authoring. Audit role and entry,not labels alone.',evidence='docs/dev/AI_CROSS_WORK_LEARNING_CONTRACT.json',result='SCOPE_RESOLVED'),
      dict(id='SCOPE-04',question='TRAIN style learning versus VALIDATION calibration',resolution='Primary profiles are fitted onTRAIN. Separate validation calibration is conditional advice,not a new style truth or production qualification;sealedHOLDOUT never fits. Negative calibration evidence must not become positive support.',evidence='template_ai/design_capacity.py',result='DISTINCT_PURPOSES;NEGATIVE_SUPPORT_DEFECT_FIXED_SEPARATELY'),
      dict(id='SCOPE-05',question='Software implemented versus real AI quality',resolution='Synthetic software mechanism and8partial/0full real-corpus qualification are distinct;do not rewrite original package counts.',evidence='docs/dev/AI_CROSS_WORK_LEARNING_CONTRACT.json',result='SCOPE_RESOLVED'),
      dict(id='SCOPE-06',question='Old singleCodex/no-billing-proof prohibition',resolution='Later included-tools decision supersedes cost blanket bans;platform/task delegation rules still apply. Current Git failure is authentication,not a budget gate.',evidence='docs/decisions/2026-10-21-INCLUDED-TOOLS-AND-EXECUTION-EFFICIENCY.md',result='SUPERSESSION_RESOLVED')
    ]
    write('rule-ledger.json',dict(kind='NORMATIVE_SCOPE_REVIEW_NOT_RUNTIME_PROOF',rules=rules,resolutions=resolutions,
                                generator_sha256=sha(Path(__file__))))
    registry=json.loads((ROOT/'docs/dev/REQUIREMENTS.json').read_text());sources=test_sources();rows=[];parent_routes={}
    for requirement in registry['requirements']:
        rid=requirement['id'];topics=set()
        for pattern,values in ROUTES:
            if re.search(pattern,requirement['title'],re.I):topics.update('NCA-'+v for v in values)
        topics.add('NCA-H01');parent_routes[rid]=topics
    for requirement in registry['requirements']:
        parent_topics=set().union(*(parent_routes.get(p,set()) for p in requirement.get('parents',[])))
        for clause in requirement['acceptance']:
            topics=set(parent_routes[requirement['id']])|parent_topics
            for pattern,values in ROUTES:
                if re.search(pattern,clause['expected'],re.I):topics.update('NCA-'+v for v in values)
            missing=[t for t in clause['tests'] if t not in sources]
            rows.append(dict(requirement_id=requirement['id'],acceptance_id=clause['id'],
               approved_expected_verbatim=clause['expected'],requirement_status=requirement['status'],
               audit_topics=sorted(topics),expected_origin='Approved requirement clause,not generated from product output.',
               original_test_ids=clause['tests'],test_assertion_anchors={t:sources[t] for t in clause['tests'] if t in sources},
               unresolved_inherited_or_missing_test_anchors=missing,
               evidence_scope='TRACEABILITY_MAP_NOT_A_NEW_ACCEPTANCE_PASS',
               external_or_unlinked_reason='Original partial/deferred scope;see unlinked-clause-dispositions.json' if not clause['tests'] else None))
    assert len(rows)==825 and len({r['acceptance_id'] for r in rows})==825
    assert all(set(r['audit_topics'])<=declared for r in rows)
    write('requirement-audit-map.json',dict(requirements=len(registry['requirements']),clauses=len(rows),
          registry_sha256=sha(ROOT/'docs/dev/REQUIREMENTS.json'),all_clauses_mapped=True,
          unlinked_clauses=sum(not r['original_test_ids'] for r in rows),
          inherited_or_missing_anchor_count=sum(len(r['unresolved_inherited_or_missing_test_anchors']) for r in rows),
          method='Deterministic trace routing by approved clause/title,parent context and existing assertion source anchors;mapping is not semantic proof or test execution.',
          rows=rows))
    write('requirement-map-summary.json',dict(requirements=len(registry['requirements']),clauses=len(rows),
         all_clauses_mapped=True,missing_expected_text=sum(not r['approved_expected_verbatim'] for r in rows),
         unlinked_clauses=[r['acceptance_id'] for r in rows if not r['original_test_ids']],
         topic_counts=dict(Counter(t for r in rows for t in r['audit_topics'])),
         inherited_or_missing_anchors=sorted({t for r in rows for t in r['unresolved_inherited_or_missing_test_anchors']}),
         no_direct_assertions=sorted({t for r in rows for t,a in r['test_assertion_anchors'].items() if not a['direct_assertion_kinds']})))
    print(json.dumps(dict(rules=len(rules),scope_resolutions=len(resolutions),requirements=len(registry['requirements']),clauses=len(rows),all_mapped=True),ensure_ascii=False))


if __name__=='__main__':
    build()
