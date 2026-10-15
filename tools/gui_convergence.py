"""Decision/implementation reconciliation, not a new product feature or report exporter."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from template_ai.diagnostic_routes import ROUTES

OWNERS={'UI-015':'OUTPUT_INPUT_PROBLEMS','UI-024':'EXISTING_LOGO_TABLE_SIZE_VIEW','UI-043':'CUSTOMER_DIALOG','UI-044':'CUSTOMER_DIALOG','UI-045':'CUSTOMER_DIALOG','UI-046':'CUSTOMER_DIALOG_COMPARE','UI-047':'CUSTOMER_DIALOG_BACKUP','UI-050':'EXISTING_SOURCE_INDEX_SCAN','UI-053':'EXISTING_TRAINING_QUALITY_EVALUATION','UI-054':'EXISTING_TRAINING_QUALITY_REPAIR','UI-058':'OUTPUT_TRANSIENT_SESSION','UI-061':'OUTPUT_CURRENT_CANDIDATE','UI-063':'EXISTING_OBJECT_PROPERTIES','UI-065':'EXISTING_OBJECT_EDITS_BATCH','UI-066':'REUSE_DIAGNOSTIC_ROUTES','UI-067':'GOVERNANCE_ONLY','UI-052-REVIEW':'EXISTING_TRAINING_SAMPLE_DEPENDENCIES'}

def reconcile(registry):
    topics=[r for r in registry['requirements'] if r['kind']=='topic'];ids=[r['id'] for r in topics]
    if len(ids)!=75 or len(set(ids))!=75:raise ValueError('原75父題不可遺失或拆分湊數')
    rows=[]
    for r in topics:
        if not r['sources']:raise ValueError('缺決策來源')
        decision='OPEN_HUMAN_DECISION' if r['status']=='BLOCKED' and r['id'].startswith('UI-066-R') else 'FUTURE_BACKLOG' if r['status']=='DEFERRED' else 'RESEARCH_OR_TEST_NEEDED' if r['id'] in ('REV-02','REV-04') else 'APPROVED_REQUIREMENT'
        rows.append({'id':r['id'],'decision_state':decision,'implementation_state':r['status'],'source':r['sources'],'owner':OWNERS.get(r['id'],'REUSE_EXISTING_OR_UNMAPPED_NO_NEW_CENTER'),'fully_verified':r['completed']})
    for r in topics:
        if r['id'] in ('UI-066-R1','UI-066-R2') and r['status']!='BLOCKED' and 'docs/decisions/2026-10-15-DIAGNOSTIC-REPORT-ADOPTED.md' not in r['sources']:
            raise ValueError('解除報告受阻需有使用者具名採納決策')
    return {'schema':1,'rows':rows,'diagnostic_routes':ROUTES,'conflicts_resolved':['UI-060跨尺寸歷史題由UI-061接手','UI-002記憶體與UI-058受控恢復為不同已核准範圍','產品統一矩形自動排版；.ai正式輸出未核准'],'open':[r['id'] for r in topics if r['status']=='BLOCKED'],'product_features_added':0,'new_order_database':False,'formal_output_formats':['PDF','PNG','JPG']}
if __name__=='__main__':
    result=reconcile(json.loads((ROOT/'docs/dev/REQUIREMENTS.json').read_text()));print(json.dumps(result,ensure_ascii=False,indent=2))
