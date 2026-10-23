"""Actual anonymous GUI evidence for the consecutive work packages."""
import copy
import json
from PySide6.QtWidgets import QApplication
from template_ai.model import Template,Slot,Rect,new_id
from template_ai.object_dialog import ObjectToolsDialog
from PySide6.QtCore import Qt


def capture_index(window,artifacts,source_work_id,template_id):
    t=copy.deepcopy(next(t for t in window.library.templates() if t.id==template_id));t.id=new_id();t.family_id=new_id();t.version=1;t.state='draft';t.name='Anonymous semantic references';t.capacity=2;t.company_bindings={'p1':'c1','p2':'c1'}
    t.slots.append(Slot('logo','c1',Rect(70,30,12,10),id='anonymous-shared-logo'))
    other=copy.deepcopy(t.slots[0]);other.id=new_id();other.owner='p2';other.rect.y=35;t.slots.append(other);window.library.save_template(t)
    dlg=ObjectToolsDialog(window,'TEMPLATE',t.id);dlg.show();QApplication.processEvents();dlg.select_ids(['anonymous-shared-logo'])
    shared=next(n for n in dlg.tree_nodes if n.data(0,Qt.UserRole)==['anonymous-shared-logo']);dlg.index_tree.scrollToItem(shared);QApplication.processEvents()
    assert dlg.grab().save(str(artifacts/'semantic-tree-shared.png'))
    before=window.library.object_snapshot('TEMPLATE',t.id);dlg.search.setText('p1 name');assert dlg.ids==['anonymous-shared-logo']
    assert dlg.grab().save(str(artifacts/'semantic-search-preserved.png'))
    dlg.search.clear();dlg.viewport_action('ISOLATE');assert before==window.library.object_snapshot('TEMPLATE',t.id)
    assert dlg.grab().save(str(artifacts/'semantic-viewport-isolated.png'))
    report={'shared_ids':dlg.ids,'db_unchanged':True,'full_slot_count':len(before['payload']['slots']),'visible_ids':sorted(set(s['id'] for s in before['payload']['slots'])-dlg.hidden_ids),'source_mapping':'UNKNOWN','scope':'Anonymous actual GUI; viewport is not output visibility or independent review'}
    dlg.viewport_action('ALL');dlg.close()
    dlg=ObjectToolsDialog(window,'ARTWORK',source_work_id);dlg.show();QApplication.processEvents();dlg.index_mode.setCurrentIndex(1)
    report['derivative']=dlg.structure;assert dlg.grab().save(str(artifacts/'semantic-derived-structure.png'));dlg.close()
    (artifacts/'semantic-index-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


def capture_batch(window,artifacts):
    import threading,time
    from unittest.mock import patch
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtTest import QTest
    from template_ai.batch_import import preflight,convert_item
    from template_ai.batch_dialog import BatchImportDialog
    folder=artifacts/'synthetic-batch-input';folder.mkdir(exist_ok=True)
    paths=[]
    for name,color in [('first.svg','red'),('second.svg','blue')]:
        p=folder/name;p.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="20" height="20" fill="{color}"/></svg>');paths.append(p)
    duplicate=folder/'duplicate.svg';duplicate.write_bytes(paths[0].read_bytes());paths.append(duplicate)
    d=BatchImportDialog(window);d.show();QApplication.processEvents();d.paths=[str(p) for p in paths];d.report=preflight(d.paths,window.library.list_sources());d.render(d.report['items']);d.summary.setText('3來源；1 exact 重複，作品／模板相似 UNKNOWN');d.controls()
    assert d.grab().save(str(artifacts/'batch-import-preflight.png'))
    entered=threading.Event();release=threading.Event()
    def gated(item,assets):entered.set();release.wait(5);return convert_item(item,assets)
    def wait_for(predicate):
        end=time.monotonic()+12
        while not predicate() and time.monotonic()<end:QTest.qWait(10)
        assert predicate(),d.status.text()
    with patch('template_ai.batch_dialog.convert_item',side_effect=gated):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.start_confirmed()
        wait_for(entered.is_set);assert d.grab().save(str(artifacts/'batch-import-running.png'));d.cancel();release.set();wait_for(lambda:not d.running and not d.busy)
    cancelled=copy.deepcopy(d.batch);assert cancelled['phase']=='CANCELLED';assert d.grab().save(str(artifacts/'batch-import-cancelled.png'));bid=cancelled['id'];d.close()
    d=BatchImportDialog(window);d.show();d.history.setCurrentIndex(d.history.findData(bid));QApplication.processEvents()
    with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.resume()
    wait_for(lambda:not d.running and not d.busy);assert d.batch['phase']=='DONE';assert d.grab().save(str(artifacts/'batch-import-resumed.png'))
    audit={'cancelled':cancelled,'resumed':d.batch,'scope':'Actual anonymous GUI; procedure-confirmed source import only, no automatic semantic training/publication or independent review'}
    (artifacts/'batch-import-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');d.close()


def capture_exceptions(window,artifacts):
    import time
    from unittest.mock import patch
    from PySide6.QtWidgets import QMessageBox,QInputDialog
    from PySide6.QtTest import QTest
    from template_ai.batch_import import preflight
    from template_ai.exception_dialog import ImportExceptionDialog
    folder=artifacts/'synthetic-exception-input';folder.mkdir(exist_ok=True);paths=[]
    for name,color in [('failed.svg','red'),('untouched.svg','blue')]:
        p=folder/name;p.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="20" height="20" fill="{color}"/></svg>');paths.append(p)
    store=window.import_store;b=store.create(preflight([str(p) for p in paths],window.library.list_sources()),True);r=b['items'][0];b=store.claim(b['id'],b['revision'],r['id']);b=store.finish(b['id'],b['revision'],r['id'],error='Synthetic controlled parse failure');b=store.stop(b['id'],b['revision']);before=copy.deepcopy(b)
    dlg=ImportExceptionDialog(window);dlg.show();QApplication.processEvents();dlg.search.setText('synthetic-exception-input');dlg.table.selectRow(0)
    assert dlg.grab().save(str(artifacts/'exception-center-ranked.png'))
    with patch.object(QInputDialog,'getText',return_value=('Anonymous exclude demonstration',True)),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dlg.change_status('EXCLUDE')
    dlg.filter.setCurrentIndex(1);dlg.table.selectRow(0);QApplication.processEvents();assert dlg.grab().save(str(artifacts/'exception-center-excluded.png'))
    with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dlg.change_status('RESTORE')
    dlg.filter.setCurrentIndex(0);dlg.table.selectRow(0);QApplication.processEvents();assert dlg.grab().save(str(artifacts/'exception-center-restored.png'))
    paths[0].write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="20" height="20" fill="green"/></svg>');dlg.preview_retry()
    def wait_for(predicate):
        end=time.monotonic()+12
        while not predicate() and time.monotonic()<end:QTest.qWait(10)
        assert predicate(),dlg.status.text()
    wait_for(lambda:not dlg.busy);assert dlg.plan,dlg.status.text();preview={'batch':dlg.plan['batch_id'],'ids':dlg.plan['ids'],'hash_differences':{i:{k:x[k] for k in ('old_hash','new_hash','changed')} for i,x in dlg.plan['items'].items()}}
    assert dlg.grab().save(str(artifacts/'exception-center-retry-preview.png'))
    with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dlg.apply_retry()
    assert dlg.runner,dlg.status.text();wait_for(lambda:not dlg.runner.running and not dlg.runner.busy);after=store.get(b['id']);assert after['items'][0]['status']=='SUCCESS' and after['items'][1]['status']=='READY';assert after['items'][1]==before['items'][1]
    assert dlg.runner.grab().save(str(artifacts/'exception-center-retried.png'));dlg.runner.close();QApplication.processEvents();dlg.close()
    (artifacts/'exception-center-audit.json').write_text(json.dumps({'before':before,'preview':preview,'after':after,'other_ready_unchanged':True,'scope':'Actual anonymous GUI and controlled test failure, not real customer data or independent review'},ensure_ascii=False,indent=2)+'\n')
