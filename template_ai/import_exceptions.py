"""Explainable import exception indexes and explicit revision-safe single-batch actions."""
import copy
from pathlib import Path
from .batch_import import preflight,MAX_BYTES
from .source_links import hash_source,check_verified,VerifiedSource


def exception_rows(library,store,query='',order='SMART',status='OPEN'):
    sources=library.list_sources();rows=[]
    for b in store.list():
        for item in b['items']:
            if item['status'] not in ('FAILED','INTERRUPTED','EXCLUDED'):continue
            if status=='OPEN' and item['status']=='EXCLUDED' or status=='EXCLUDED' and item['status']!='EXCLUDED':continue
            ids=set()
            reuse_id=(item.get('reuse_source') or {}).get('id')
            for s in sources:
                if s['id'] in (item.get('source_id'),reuse_id):
                    ids.add(s['id'])
                if (s['hash']==item.get('expected_hash') and s['page']==item['page']) or Path(s['current_path']).absolute()==Path(item['path']).absolute():ids.add(s['id'])
            impacts={key:set() for key in ('work_ids','template_ids','logo_ids')}
            for sid in ids:
                info=library.source_impacts(sid)
                for key in impacts:impacts[key].update(info[key])
            impacts={k:sorted(v) for k,v in impacts.items()};count=sum(len(v) for v in impacts.values())
            error_type=item.get('error_type','IMPORT');level=3 if error_type=='INTEGRITY' else 2 if error_type in ('SOURCE_CHANGED','CACHE_CHANGED','INTERRUPTED') else 1
            if item['status']=='EXCLUDED':level=0
            row={'key':b['id']+'/'+item['id'],'batch_id':b['id'],'revision':b['revision'],'batch_phase':b['phase'],'item':copy.deepcopy(item),'source_ids':sorted(ids),'impacts':impacts,'impact_count':count,'customer_impact':'UNKNOWN','severity':level,'type':error_type,'ranking_reason':f'嚴重度{level}；exact登錄依賴 作品{len(impacts["work_ids"])}／模板{len(impacts["template_ids"])}／Logo{len(impacts["logo_ids"])}；客戶／尚未建檔影響UNKNOWN','dependency_basis':'登錄source ID／相同hash+page或目前路徑，依賴ID去重；不是AI推測品質影響'}
            words=' '.join([row['key'],item['path'],item['reason'],item['status'],error_type,*ids]).casefold()
            if all(t in words for t in query.casefold().split()):rows.append(row)
    key=lambda r:(-r['severity'],-r['impact_count'],r['item']['path'].casefold(),r['key'])
    if order=='SOURCE':key=lambda r:(r['item']['path'].casefold(),-r['severity'],r['key'])
    elif order=='TYPE':key=lambda r:(r['type'],-r['severity'],-r['impact_count'],r['key'])
    return sorted(rows,key=key)


def prepare_retry(rows,sources):
    if not rows or len({r['batch_id'] for r in rows})!=1:raise ValueError('一次核對一個批次，不能暗拆跨批次範圍')
    if len({r['key'] for r in rows})!=len(rows):raise ValueError('選取ID重複')
    if any(r['item']['status'] not in ('FAILED','INTERRUPTED') for r in rows):raise ValueError('只重試FAILED／INTERRUPTED；已排除需先明確恢復')
    items={}
    for r in rows:
        item=r['item'];report=preflight([item['path']],sources,item['page']);new=report['items'][0]
        if new['status']!='READY':raise ValueError('重試預檢未通過：'+new['reason'])
        proof=hash_source(item['path'],byte_limit=MAX_BYTES)
        if proof.hash!=new['expected_hash']:raise ValueError('預檢後來源異動')
        items[item['id']]={'proof':proof,'old_hash':item.get('expected_hash'),'new_hash':proof.hash,'changed':proof.hash!=item.get('expected_hash'),'reuse_source':new.get('reuse_source')}
    return {'batch_id':rows[0]['batch_id'],'revision':rows[0]['revision'],'ids':sorted(items),'items':items}


def apply_action(store,batch_id,revision,ids,action,reason='',plan=None,confirmed=False):
    if not confirmed:raise ValueError('每次動作需明確核對並確認')
    if not ids or len(ids)>200 or len(set(ids))!=len(ids):raise ValueError('需明列唯一1～200項ID')
    if action not in ('RETRY','EXCLUDE','RESTORE'):raise ValueError('例外動作不合法')
    if action=='EXCLUDE' and (not reason.strip() or len(reason)>500):raise ValueError('排除需1～500字原因')
    def change(b):
        if b['phase']=='RUNNING' or any(r['status']=='RUNNING' for r in b['items']):raise ValueError('批次仍在執行，不接管或重複啟動')
        selected=[r for r in b['items'] if r['id'] in ids]
        if len(selected)!=len(ids):raise ValueError('ID不屬本批，未修改任何項')
        allowed={'RETRY':('FAILED','INTERRUPTED'),'EXCLUDE':('FAILED','INTERRUPTED'),'RESTORE':('EXCLUDED',)}[action]
        if any(r['status'] not in allowed for r in selected):raise ValueError('精確選取包含不可處理項，請重新核對')
        if any(r.get('error_type')=='INTEGRITY' for r in selected):
            if store.db.execute('PRAGMA quick_check').fetchall()!=[('ok',)] or store.db.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('資料完整性仍受阻，不能排除／重試來解除整批保護')
        if action=='RETRY':
            if not plan or plan['batch_id']!=batch_id or plan['revision']!=revision or set(plan['ids'])!=set(ids) or set(plan['items'])!=set(ids):raise ValueError('重試核對票據／精確範圍不符')
            for r in selected:
                proof=plan['items'][r['id']]['proof']
                if not isinstance(proof,VerifiedSource) or proof.path!=str(Path(r['path']).resolve()) or proof.stat[2]>MAX_BYTES or plan['items'][r['id']]['old_hash']!=r.get('expected_hash'):raise ValueError('來源票據不屬此項')
                check_verified(proof,plan['items'][r['id']]['new_hash'])
        for r in selected:
            previous={'status':r['status'],'reason':r['reason'],'hash':r.get('expected_hash'),'error_type':r.get('error_type'),'source_id':r.get('source_id')}
            r['history'].append({'action':action,'previous':previous,'reason':reason,'attempt':r['attempts']})
            if action=='EXCLUDE':r.update(status='EXCLUDED',excluded_from=previous,reason='明確排除：'+reason+'；不等於成功／可信樣本或規則批准')
            elif action=='RESTORE':
                old=r['excluded_from'];r.update(status=old['status'],reason=old['reason']);r.pop('excluded_from',None)
            else:
                item_plan=plan['items'][r['id']];r.update(status='READY',expected_hash=item_plan['new_hash'],reuse_source=copy.deepcopy(item_plan['reuse_source']),reason='精確核對重試；仍待實際轉換結果',source_id=None);r.pop('error_type',None)
                r['history'][-1]['approved_hash']=item_plan['new_hash']
        b['phase']='READY' if any(r['status']=='READY' for r in b['items']) else 'DONE_WITH_ERRORS' if any(r['status'] in ('FAILED','INTERRUPTED') for r in b['items']) else 'DONE_WITH_EXCLUSIONS' if any(r['status']=='EXCLUDED' for r in b['items']) else 'DONE';b['owner']=None
    return store.mutate(batch_id,revision,'import_exception_'+action.lower()+'_confirmed',change)
