"""Actual anonymous GUI evidence for the consecutive work packages."""
import copy
import json
from PySide6.QtWidgets import QApplication
from template_ai.model import Template,Slot,Rect,new_id
from template_ai.object_dialog import ObjectToolsDialog


def capture_index(window,artifacts,source_work_id,template_id):
    t=copy.deepcopy(next(t for t in window.library.templates() if t.id==template_id));t.id=new_id();t.family_id=new_id();t.version=1;t.state='draft';t.name='Anonymous semantic references';t.capacity=2;t.company_bindings={'p1':'c1','p2':'c1'}
    t.slots.append(Slot('logo','c1',Rect(70,30,12,10),id='anonymous-shared-logo'))
    other=copy.deepcopy(t.slots[0]);other.id=new_id();other.owner='p2';other.rect.y=35;t.slots.append(other);window.library.save_template(t)
    dlg=ObjectToolsDialog(window,'TEMPLATE',t.id);dlg.show();QApplication.processEvents();dlg.select_ids(['anonymous-shared-logo'])
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
