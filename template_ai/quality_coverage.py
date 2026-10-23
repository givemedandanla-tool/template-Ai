"""Bounded descriptive inventory. Counts are never quality thresholds or supplementation advice."""
from collections import Counter,defaultdict
from pathlib import Path
import math
import re


class CoverageMixin:
    def coverage_report(self,offset=0,limit=200):
        from .training_store import digest
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=200:raise ValueError('分頁最多200，需明列有效範圍')
        totals={'sources':self.db.execute('SELECT count(*) FROM sources').fetchone()[0],'artworks':self.db.execute('SELECT count(*) FROM artworks').fetchone()[0],'sources_without_artworks':self.db.execute('SELECT count(*) FROM sources s WHERE NOT EXISTS(SELECT 1 FROM artworks a WHERE a.source_id=s.id)').fetchone()[0],'fact_records':self.count('FACTS'),'stored_samples':self.count('SAMPLE'),'datasets':self.count('DATASET')}
        source_ids=[r[0] for r in self.db.execute('SELECT id FROM sources ORDER BY id LIMIT ? OFFSET ?',(limit,offset))];work_ids=[r[0] for r in self.db.execute('SELECT id FROM artworks ORDER BY id LIMIT ? OFFSET ?',(limit,offset))];samples=self.records('SAMPLE',offset,limit);sample_states={s['id']:self.sample_state(s['id']) for s in samples};works=[];sources=[];facets=defaultdict(lambda:defaultdict(list))
        for sid in source_ids:
            source=self.library.source(sid);wid=self.db.execute("SELECT id FROM training_records WHERE kind='FACTS' AND json_extract(payload,'$.pins.source_id')=? ORDER BY id LIMIT 1",(sid,)).fetchone();state='CONTENT_VERIFIED_BY_CURRENT_FACTS' if wid and self.facts_state(wid[0])=='CONFIRMED' else 'CURRENT_HEALTH_UNKNOWN'
            try:
                if not Path(source['current_path']).is_file():state='SOURCE_MISSING'
            except OSError:state='CURRENT_HEALTH_UNKNOWN'
            sources.append({'source_id':sid,'registered_content_group':source['hash'],'health':state,'derivative_health':'UNKNOWN_AT_INVENTORY; no pixels loaded','artwork_count':self.db.execute('SELECT count(*) FROM artworks WHERE source_id=?',(sid,)).fetchone()[0]})
        for wid in work_ids:
            work=self.library.artwork(wid);payload=work['payload'];source=self.library.source(work['source_id']);slots=payload['slots'];people={s.get('owner') for s in slots if isinstance(s,dict) and re.fullmatch(r'p[1-9][0-9]*',str(s.get('owner','')))};companies={s.get('owner') for s in slots if isinstance(s,dict) and re.fullmatch(r'c[1-9][0-9]*',str(s.get('owner','')))}
            dimensions=(payload.get('work_width'),payload.get('work_height'));known_dims=all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in dimensions);size=f'{dimensions[0]:g}×{dimensions[1]:g}mm' if known_dims else 'UNKNOWN';logo='LOGO_LABELLED; NATIVE_CONTENT_UNKNOWN' if any(isinstance(s,dict) and s.get('kind')=='logo' for s in slots) else 'NO_LOGO_LABEL; SOURCE_CONTENT_UNKNOWN'
            row={'work_id':wid,'source_id':work['source_id'],'work_revision':work['revision'],'registered_content_group':source['hash'],'size':size,'people_count':len(people),'company_count':len(companies),'logo_class':logo,'native_effects':'UNKNOWN','facts_state':self.facts_state(wid),'customer_identity':'UNKNOWN'};works.append(row)
            for axis,value in (('size',size),('people',str(len(people))),('companies',str(len(companies))),('logo',logo),('content_group',source['hash']),('native_effects','UNKNOWN')):facets[axis][value].append(wid)
        saved_roles=Counter({r[0] or 'UNKNOWN':r[1] for r in self.db.execute("SELECT json_extract(e.value,'$.role'),count(*) FROM training_records d,json_each(d.payload,'$.entries') e WHERE d.kind='DATASET' GROUP BY json_extract(e.value,'$.role')")});current_roles=Counter();role_unknown=0;dataset_page=self.records('DATASET',offset,limit)
        for ds in dataset_page:
            manifest_current=digest(ds.get('manifest'))==ds.get('manifest_digest') and ds.get('entries')==ds.get('manifest',{}).get('entries')
            for entry in ds.get('entries',[]):
                state=sample_states.get(entry.get('sample_id'))
                sample=next((s for s in samples if s['id']==entry.get('sample_id')),None)
                if manifest_current and state=='APPROVED' and sample and sample['revision']==entry.get('sample_revision'):current_roles[entry['role']]+=1
                else:role_unknown+=1
        counts=Counter(sample_states.values());complete=all(offset==0 and total<=limit for total in (totals['sources'],totals['artworks'],totals['stored_samples'],totals['datasets']))
        notices=[]
        if counts['APPROVED']==0:notices.append('本掃描範圍無有效准入樣本；不是品質判定或正式無解')
        if not complete:notices.append('有界分頁未涵蓋全庫，目前資格與分布僅本頁，SQL總數另列')
        if works:notices.append('原生Logo／效果、客戶歸屬与代表性未知，不能用數量當品質驗收')
        report={'totals':totals,'scan':{'offset':offset,'limit':limit,'sources':len(sources),'artworks':len(works),'samples':len(samples),'datasets':len(dataset_page),'complete_inventory':complete},'sources':sources,'artworks':works,'sample_states':dict(sorted(counts.items())),'sample_rows':[{'sample_id':s['id'],'work_id':s.get('work_id','UNKNOWN'),'state':sample_states[s['id']]} for s in samples],'saved_dataset_role_occurrences':dict(sorted(saved_roles.items())),'current_role_occurrences_in_scanned_scope':dict(sorted(current_roles.items())),'unvalidated_role_occurrences_in_scanned_datasets':role_unknown,'facets':{axis:{value:sorted(ids) for value,ids in sorted(values.items())} for axis,values in sorted(facets.items())},'facet_denominator':'SCANNED_ARTWORKS; axes overlap, never sum as distinct classes','role_denominator':'MANIFEST_ENTRY_OCCURRENCES; same sample may appear in multiple frozen datasets','notices':notices,'supplementation':False,'quality_pass_claim':False,'images_loaded':False}
        report['snapshot_digest']=digest(report);return report
