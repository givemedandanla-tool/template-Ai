"""Actual anonymous Qt entity/customer flow; databases and inputs remain local."""
import argparse
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.gui import MainWindow
from template_ai.input_graph import InputGraph
from template_ai.input_graph_dialog import InputGraphDialog
from template_ai.customer_dialog import CustomerDialog
from template_ai.customers import CustomerStore
from template_ai.model import Template,Slot,Rect


def capture(root):
    app=QApplication.instance() or QApplication([]);root=Path(root);root.mkdir(parents=True,exist_ok=True)
    w=MainWindow(root/'entity-local-data');g=InputGraph.from_legacy([dict(name=['Alex Example'],phone=['020-000-0100'],company='c1'),dict(name=['Casey Example'],phone=['020-000-0100'],company='c1')],[dict(name='Example Company',phone=['020-000-0200'])])
    pid=g.data['people'][0]['id'];g.command('add_company',person_id=pid,name='Second Example Company');d=InputGraphDialog(w,g.data);d.show();app.processEvents();assert d.grab().save(str(root/'entity-person-cards.png'))
    cid=g.data['companies'][0]['id'];assert not d.execute('delete_company',company_id=cid)
    with patch('template_ai.input_graph_dialog.QMessageBox.question',return_value=QMessageBox.Yes):assert d.execute('unlink_company',person_id=pid,company_id=cid)
    d.undo();assert [pid,cid] in d.graph.data['links'];d.accept();w.adopt_input_graph(d.graph.data);w.tabs.setCurrentIndex(2);w.show();app.processEvents();assert w.grab().save(str(root/'entity-adopted-input.png'))
    t=Template('Synthetic exact style',90,54,[Slot('name','p1',Rect(3,3,40,7)),Slot('name','p2',Rect(3,15,40,7))],capacity=2);w.library.save_template(t);store=CustomerStore(w.library);master=store.create_graph('00123','Synthetic Example Client',g.data,t.id,True)
    draft=store.reorder(master['id'],master['styles'][0]['id'],True);w.adopt_input_graph(draft['graph'],master);phone=next(f for f in w.active_input_graph.data['fields'] if f['kind']=='phone');w.active_input_graph.command('edit_field',field_id=phone['id'],value='020-000-0300');w.adopt_input_graph(w.active_input_graph.data)
    c=CustomerDialog(w);c.query.setText('00123');c.search();c.customers.selectRow(0);c.show();app.processEvents();c.preview();assert '020-000-0300' in c.details.toPlainText();assert c.grab().save(str(root/'entity-customer-diff.png'));assert store.get(master['id'])==master
    audit={'schema_version':1,'evidence_kind':'ACTUAL_QT_ENTITY_AND_CUSTOMER_WORKFLOW','anonymous_synthetic_only':True,'person_count':len(g.data['people']),'company_count':len(g.data['companies']),'many_company_root':True,'shared_company_delete_refused':True,'unlink_undo_preserved':True,'stable_field_diff_from_actual_work':True,'master_unchanged_by_work_edit':True,'formal_output_still_disabled':not w.export_button.isEnabled(),'databases_exported':False,'raw_ids_exported':False}
    (root/'entity-gui-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    c.hide();d.hide();w.hide();w.input_timer.stop();w.library.db.close();print(json.dumps(audit))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts-dir',required=True);capture(parser.parse_args().artifacts_dir)
