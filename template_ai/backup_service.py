"""Orchestrate authenticated file creation and following local receipts."""
from pathlib import Path
import tempfile
import sqlite3
import json
import hashlib
from contextlib import closing

from . import relational_backup as bundle,backup_policy as policy
from .background import file_digest


def perform_backup(library,target,password,options=None,plan=None,allow_partial=False,retention_settings=None,
                   cancel=lambda:False,progress=None):
    plan=plan or bundle.plan_backup(library,**(options or {}),cancel=cancel,progress=progress)
    result=bundle.create_backup(library,target,password,plan,True,allow_partial,cancel,progress)
    output=dict(backup=result,history_state='PENDING',retention=None)
    try:
        output['receipt']=policy.record_result(library,result);output['history_state']='RECORDED'
    except Exception as error:
        output.update(history_state='FILE_CREATED_RECEIPT_FAILED',history_error=str(error));return output
    if retention_settings:
        try:
            output['retention']=policy.retention(library,Path(target).parent,password,
                retention_settings['retain_count'],retention_settings['retain_days'],True,cancel=cancel)
        except Exception as error:output['retention']=dict(state='FAILED',reason=str(error))
    return output


def relational_checks(root):
    """Semantic IDs and version fingerprints in addition to SQLite FKs."""
    root=Path(root);issues=[];counts=dict(templates=0,styles=0,source_associations=0,primary_customers=0)
    with closing(sqlite3.connect((root/'library.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        tables=bundle._tables(db);bundle._integrity(db)
        templates={}
        for identity,payload in db.execute('SELECT id,payload FROM templates'):
            templates[identity]=hashlib.sha256(bundle._json(json.loads(payload))).hexdigest()
        counts['templates']=len(templates)
        if 'customer_styles' in tables:
            for identity,template,expected in db.execute('SELECT id,template_id,template_hash FROM customer_styles'):
                counts['styles']+=1
                if templates.get(template)!=expected:issues.append(dict(id=identity,kind='STYLE_VERSION_REVALIDATION_REQUIRED'))
        if 'customer_source_associations' in tables:
            for identity,template,expected,source_hash,current_hash in db.execute('SELECT a.id,a.template_id,a.template_hash,a.source_hash,s.hash FROM customer_source_associations a JOIN sources s ON s.id=a.source_id'):
                counts['source_associations']+=1
                if templates.get(template)!=expected or source_hash!=current_hash:issues.append(dict(id=identity,kind='SOURCE_STYLE_RELATION_REVALIDATION_REQUIRED'))
        if {'customers','customer_entities','customer_graph_states'}<=tables:
            from .customer_entities import read_graph
            sql='SELECT id,revision FROM customers'
            if 'customer_identity_redirects' in tables:sql+=' WHERE NOT EXISTS (SELECT 1 FROM customer_identity_redirects d WHERE d.secondary_id=customers.id)'
            for identity,revision in db.execute(sql):
                counts['primary_customers']+=1
                if read_graph(db,identity,revision) is None:issues.append(dict(id=identity,kind='OWNERSHIP_REVIEW_REQUIRED'))
        result=dict(database_integrity='PASS',counts=counts,version_or_ownership_issues=issues,
                    state='RELATIONS_PASS' if not issues else 'RELATIONS_REVIEW_REQUIRED',
                    training_state='PRESERVED_REVALIDATION_REQUIRED',production_ready=False)
    return result


def test_restore(library,record,password,cancel=lambda:False,progress=None):
    policy.verify_record(record,password)
    with tempfile.TemporaryDirectory(prefix='template-ai-isolated-restore-test-') as temporary:
        report=bundle.restore_bundle(record['path'],Path(temporary)/'test',password,True,True,cancel,progress,record['sha256'])
        validation=relational_checks(report['library_root'])
        outcome=dict(test_restore=True,state='ISOLATED_TEST_COMPLETED',validation=validation,
                     complete_assets=report['complete_assets'],temporary_copy_removed=True,production_ready=False)
    old=policy.history(library);updated=[dict(r,test_restore=True,last_test_restore=outcome) if r['id']==record['id'] and r['sha256']==record['sha256'] else r for r in old]
    policy._save(library,policy.HISTORY,updated,old)
    return outcome
