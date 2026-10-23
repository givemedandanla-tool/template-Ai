"""Explicit current human-truth binding; old failed receipts remain unchanged."""
import copy,time
from .training_store import digest,text
from .quality_sets import QualitySets
from .quality_protocol import QualityProtocols

KIND='QUALITY_REPAIR_TRUTH_REVIEW'


def plan(service,issue_id,dataset_id,reason):
    text(reason,'更新人工真值的原稿核對與歷史重審依據',2000)
    issue=service.current_issue(issue_id)
    if issue['evidence']['origin']!='ACTUAL_QUALITY_CASE':raise ValueError('新版真值需綁定實際原始失敗；原稿疑義先取得失敗憑證')
    protocol=QualityProtocols(service.library).get(issue['evidence']['protocol_id'])
    original=service.store.get('QUALITY_SET',protocol['scope']['dataset_id'])
    checked=QualitySets(service.library).validity(dataset_id,exposure_policy='DESCRIPTIVE_REPAIR_ONLY')
    if not checked['valid']:raise ValueError('新的人工真值／原稿／用途／家族版本仍不可核對：'+'；'.join(checked['errors']))
    dataset=checked['dataset']
    if dataset['manifest'].get('evaluation_role','HOLDOUT')!='HOLDOUT' or dataset['manifest']['declared_content_hashes']!=original['manifest']['declared_content_hashes']:raise ValueError('新版真值需同一批實際來源內容及原HOLDOUT角色，不得換資料或改作訓練')
    if not service.store.get('HOLDOUT_EXPOSED',original['id']):raise ValueError('原問題答案尚未明確揭露；需保留曝露界線')
    state=service.source_state(issue['evidence']['work_id'])
    if not state['human_truth_current']:raise ValueError('需先完成現有原稿事實人工更正／確認')
    golds=[service.store.get('QUALITY_GOLD',entry['gold_id']) for entry in dataset['entries']]
    relevant=[gold for gold in golds if gold['source_id']==issue['evidence']['source_id']]
    if not relevant or not any(gold['work_id']==issue['evidence']['work_id'] for gold in relevant):raise ValueError('新版真值未涵蓋原失敗作品／完整來源')
    if any(gold['domain_truth'].get(issue['evidence']['row']['domain'])!='MANUALLY_VERIFIED' for gold in relevant):raise ValueError('失敗領域的新人工真值仍未核實')
    result=dict(issue_id=issue_id,issue_digest=digest(issue),dataset_id=dataset_id,dataset_revision=dataset['revision'],
                dataset_manifest_digest=dataset['manifest_digest'],source_state=state,
                gold_refs=[dict(id=gold['id'],revision=gold['revision'],digest=digest(gold)) for gold in relevant],
                reason=reason,old_failure_preserved=True,holdout_exposure_reset=False,training_admission=False,quality_pass=False)
    result['digest']=digest(result);return result


def confirm(service,preview,actor,approved=False):
    if approved is not True:raise ValueError('需明確核對新版人工真值；不修改舊失敗／不解除曝露')
    text(actor,'新版真值核對者',120)
    with service.store.transaction():
        if plan(service,preview['issue_id'],preview['dataset_id'],preview['reason'])!=preview:raise ValueError('新版人工真值／來源／原問題已改變')
        prior=service.store.get(KIND,preview['issue_id'])
        return service.store._write(KIND,preview['issue_id'],dict(plan=copy.deepcopy(preview),actor=actor,at=time.time()),prior['revision'] if prior else 0,'repair_current_human_truth_explicitly_bound_old_failure_preserved')


def checked(service,issue_id):
    record=service.store.get(KIND,issue_id)
    if record and plan(service,issue_id,record['plan']['dataset_id'],record['plan']['reason'])!=record['plan']:raise ValueError('新版人工真值核對已失效，需重新明確核對')
    return record
