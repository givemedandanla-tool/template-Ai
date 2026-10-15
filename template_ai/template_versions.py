"""Compare saved versions and restore as a new draft with atomic provenance."""
from copy import deepcopy
import json
import time
from .model import Template,new_id
from .training_store import TrainingStore,digest,text


def differences(left,right):
    if left['family_id']!=right['family_id']:raise ValueError('版本差異只比較同一模板身分')
    result=[];a={s['id']:s for s in left['slots']};b={s['id']:s for s in right['slots']}
    for identity in sorted(set(a)|set(b)):
        if a.get(identity)!=b.get(identity):result.append(dict(scope='OBJECT',id=identity,before=deepcopy(a.get(identity)),after=deepcopy(b.get(identity))))
    for key in sorted((set(left)|set(right))-{'slots','id','version','state'}):
        if left.get(key)!=right.get(key):result.append(dict(scope='TEMPLATE',id=key,before=deepcopy(left.get(key)),after=deepcopy(right.get(key))))
    return result


class TemplateVersions:
    def __init__(self,library):self.library=library;self.store=TrainingStore(library)

    def plan(self,template_id):
        snapshot=self.library.object_snapshot('TEMPLATE',template_id);family=snapshot['payload']['family_id']
        result=dict(source=snapshot,next_version=self.library.next_version(family),scope='NEW_DRAFT_SAME_FAMILY; EXISTING_PUBLISHED_UNCHANGED')
        result['digest']=digest(result);return result

    def clone(self,plan,actor,reason,approved=False,rollback=False,geometry=None,custom_evidence=None):
        if approved is not True:raise ValueError('建立版本／回退草稿需明確操作')
        text(actor,'操作者',120);text(reason,'版本理由')
        with self.store.transaction():
            fresh=self.plan(plan['source']['id'])
            if fresh['digest']!=plan.get('digest'):raise ValueError('來源版本或版次已變更，請重新核對')
            template=Template.from_dict(deepcopy(fresh['source']['payload']));source_id=template.id;template.id=new_id();template.version=fresh['next_version'];template.state='draft'
            changes=[]
            if geometry is not None:
                from .object_tools import propose
                if not isinstance(geometry,dict) or not geometry:raise ValueError('需明列特製變動框位')
                for identity,rect in sorted(geometry.items()):
                    if set(rect)!={'x','y','w','h'}:raise ValueError('特製僅授權幾何，不改文字、字級或歸屬')
                    proposal=propose(template.to_dict(),'TEMPLATE',dict(operation='PATCH',ids=[identity],patch=rect));template=Template.from_dict(proposal['after']);changes.extend(proposal['changes'])
            self.library._template_provenance(template)
            self.library.db.execute('INSERT INTO templates VALUES(?,?,?,?,?)',(template.id,template.family_id,template.version,template.state,json.dumps(template.to_dict(),ensure_ascii=False)))
            self.library._bump_template_clock(template.id);self.library.event(template.id,'rollback_as_new_draft' if rollback else 'same_family_new_version_draft')
            self.store._write('TEMPLATE_VERSION',new_id(),dict(source_template_id=source_id,source_revision=fresh['source']['revision'],source_digest=digest(fresh['source']['payload']),
                target_template_id=template.id,family_id=template.family_id,target_version=template.version,action='CUSTOM_LAYOUT_DRAFT' if geometry else 'ROLLBACK_AS_NEW_DRAFT' if rollback else 'NEW_VERSION',custom_evidence=custom_evidence,geometry_changes=changes,actor=actor,reason=reason,created=time.time(),publication='NOT_PUBLISHED'),0,'template_version_provenance_saved')
            return template
