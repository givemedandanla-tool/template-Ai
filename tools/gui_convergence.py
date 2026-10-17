"""Decision/implementation reconciliation, not a new product feature or report exporter."""
import ast,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from template_ai.diagnostic_routes import ROUTES

DECISION_STATES={'APPROVED_REQUIREMENT','OPEN_HUMAN_DECISION','RESEARCH_OR_TEST_NEEDED','FUTURE_BACKLOG','CONFLICT_OR_STALE_REFERENCE'}

OWNERS={'UI-015':'OUTPUT_INPUT_PROBLEMS','UI-024':'EXISTING_LOGO_TABLE_SIZE_VIEW','UI-043':'CUSTOMER_DIALOG','UI-044':'CUSTOMER_DIALOG','UI-045':'CUSTOMER_DIALOG','UI-046':'CUSTOMER_DIALOG_COMPARE','UI-047':'CUSTOMER_DIALOG_BACKUP','UI-050':'EXISTING_SOURCE_INDEX_SCAN','UI-053':'EXISTING_TRAINING_QUALITY_EVALUATION','UI-054':'EXISTING_TRAINING_QUALITY_REPAIR','UI-058':'OUTPUT_TRANSIENT_SESSION','UI-061':'OUTPUT_CURRENT_CANDIDATE','UI-063':'EXISTING_OBJECT_PROPERTIES','UI-065':'EXISTING_OBJECT_EDITS_BATCH','UI-066':'REUSE_DIAGNOSTIC_ROUTES','UI-067':'GOVERNANCE_ONLY','UI-052-REVIEW':'EXISTING_TRAINING_SAMPLE_DEPENDENCIES'}

def reconcile(registry):
    topics=[r for r in registry['requirements'] if r['kind']=='topic'];ids=[r['id'] for r in topics]
    if len(ids)!=75 or len(set(ids))!=75:raise ValueError('原75父題不可遺失或拆分湊數')
    rows=[]
    for r in topics:
        if not r['sources']:raise ValueError('缺決策來源')
        decision='OPEN_HUMAN_DECISION' if r['status']=='BLOCKED' and r['id'].startswith('UI-066-R') else 'FUTURE_BACKLOG' if r['status']=='DEFERRED' else 'RESEARCH_OR_TEST_NEEDED' if r['id'] in ('REV-02','REV-04') else 'APPROVED_REQUIREMENT'
        rows.append({'id':r['id'],'decision_state':decision,'implementation_state':r['status'],'source':r['sources'],'owner':OWNERS.get(r['id'],'REUSE_EXISTING_OR_UNMAPPED_NO_NEW_CENTER'),'registry_completion_claim':r['completed'],'fully_verified':False,'verification_state':'REQUIRES_CURRENT_SOURCE_EVIDENCE_GATE'})
    for r in topics:
        if r['id'] in ('UI-066-R1','UI-066-R2') and r['status']!='BLOCKED' and 'docs/decisions/2026-10-15-DIAGNOSTIC-REPORT-ADOPTED.md' not in r['sources']:
            raise ValueError('解除報告受阻需有使用者具名採納決策')
    return {'schema':1,'rows':rows,'diagnostic_routes':ROUTES,'conflicts_resolved':['UI-060跨尺寸歷史題由UI-061接手','UI-002記憶體與UI-058受控恢復為不同已核准範圍','產品統一矩形自動排版；.ai正式輸出未核准'],'open':[r['id'] for r in topics if r['status']=='BLOCKED'],'product_features_added':0,'new_order_database':False,'formal_output_formats':['PDF','PNG','JPG']}

CONFLICTS=[
    {'id':'X-01','prior_state':'CONFLICT_OR_STALE_REFERENCE','resolution':'RESOLVED','scope':'UI002 memory switching with later UI058 limited controlled recovery; no permanent order store','authority':'docs/UI_DECISIONS.md'},
    {'id':'X-02','prior_state':'CONFLICT_OR_STALE_REFERENCE','resolution':'RESOLVED','scope':'Formal formats PDF/PNG/JPG only; examples mentioning AI do not authorize AI output','authority':'docs/REQUIREMENTS_BASELINE.md'},
    {'id':'X-03','prior_state':'CONFLICT_OR_STALE_REFERENCE','resolution':'RESOLVED','scope':'Historical UI060 sync belongs to UI061; UI060A owns result presentation','authority':'docs/decisions/UI-061-CROSS-CANDIDATE-SIZE-SYNC.md'},
    {'id':'X-04','prior_state':'CONFLICT_OR_STALE_REFERENCE','resolution':'RESOLVED','scope':'One rectangle model; namecard/access-card naming closed by explicit later revision; original physical constraints retained','authority':'docs/decisions/2026-10-12-RECTANGULAR-LAYOUT-VISUAL-IMPORT.md'},
    {'id':'X-05','prior_state':'CONFLICT_OR_STALE_REFERENCE','resolution':'RESOLVED','scope':'Panels/shortcuts/batch/font requirements already approved; report R1/R2 adopted2026-10-15, do not re-ask','authority':'docs/decisions/2026-10-15-DIAGNOSTIC-REPORT-ADOPTED.md'},
    {'id':'X-06','prior_state':'CONFLICT_OR_STALE_REFERENCE','resolution':'RESOLVED','scope':'UI043 persistent master data differs from UI058 short-lived transient recovery','authority':'docs/UI_DECISIONS.md'},
]


def traceability(registry,root=ROOT):
    """Reconcile exact links, not an execution/coverage or product-quality claim."""
    from dev_governance import test_ids
    root=Path(root);result=reconcile(registry);known=test_ids(root)
    covers={}
    for path in (root/'docs/dev').glob('*_CLAUSE_COVERAGE.json'):
        data=json.loads(path.read_text());parent=data.get('parent')
        if parent in covers:raise ValueError('Duplicate original parent coverage')
        covers[parent]=(path,data)
    topics={r['id']:r for r in registry['requirements'] if r['kind']=='topic'}
    for row in result['rows']:
        requirement=topics[row['id']];acceptance=requirement['acceptance'];tests={t for a in acceptance for t in a['tests']}
        coverage=covers.get(row['id'])
        if coverage:
            path,data=coverage;row['clause_mapping']=str(path.relative_to(root))
            clauses=data.get('clauses',[])
            tests.update(t for c in clauses if isinstance(c,dict) for t in c.get('tests',[]))
            row['mapped_original_clauses']=len(clauses)
            source=data.get('source');expected=data.get('source_sha256')
            if source and expected and not source.startswith('https://'):
                actual=root/source
                if not actual.is_file():raise ValueError('Missing original source mapping: '+row['id'])
                whole=hashlib.sha256(actual.read_bytes()).hexdigest()
                section=None
                if actual.suffix=='.json':
                    value=json.loads(actual.read_text()).get('original_clauses',{}).get(row['id'])
                    if isinstance(value,str):section=hashlib.sha256(value.encode()).hexdigest()
                if expected not in (whole,section):raise ValueError('Stale original source mapping: '+row['id'])
                row['original_source_hash_scope']='WHOLE_FILE' if expected==whole else 'ORIGINAL_PARENT_SECTION'

        else:row['mapped_original_clauses']=len(acceptance)
        unknown=tests-known
        if unknown:raise ValueError('Unknown test link: '+sorted(unknown)[0])
        components=set()
        for module in {t.split('.')[0] for t in tests}:
            tree=ast.parse((root/'tests'/(module+'.py')).read_text())
            for node in ast.walk(tree):
                modules=[node.module] if isinstance(node,ast.ImportFrom) else [n.name for n in node.names] if isinstance(node,ast.Import) else []
                for imported in modules:
                    if imported and imported.startswith('template_ai.'):
                        candidate=root/(imported.replace('.','/')+'.py')
                        if candidate.is_file():components.add(str(candidate.relative_to(root)))
        row.update(exact_test_ids=sorted(tests),components_referenced_by_tests=sorted(components),
                   acceptance_clause_count=len(acceptance),evidence_run=requirement.get('evidence_run'),
                   trace_state='MAPPED_NOT_EXECUTION_VERIFIED' if tests else 'MISSING_EXACT_TEST_MAPPING')
    for conflict in CONFLICTS:
        if not (root/conflict['authority']).is_file():raise ValueError('Missing conflict authority')
    result.update(schema=2,decision_states=sorted(DECISION_STATES),conflicts=CONFLICTS,
        human_decisions=[r['id'] for r in result['rows'] if r['decision_state']=='OPEN_HUMAN_DECISION'],
        research=['REV-02 authorized real nativeAI corpus plus trustworthy same-scope reference and actual learning','REV-04 actual Windows upper16GB RTX5050 and specified VivoBook benchmarks','Windows actual IME/accessibility/font installation/active-face/undo qualification'],
        future_backlog=['UI056D advanced sample collection','UI048 full roles after core software','REV03 P10 physical printing'],
        implementation_verification_independent=True,coverage_inference=False)
    return result


if __name__=='__main__':
    result=traceability(json.loads((ROOT/'docs/dev/REQUIREMENTS.json').read_text()))
    print(json.dumps(result,ensure_ascii=False,indent=2))
