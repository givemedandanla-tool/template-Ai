"""Actual catalog, source preview, comparison and exact reorder with synthetic data."""
import argparse,copy,json,os,sys,time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.gui import MainWindow
from template_ai.demo import demo_template
from template_ai.model import Rect,new_id
from template_ai.layout import generate
from template_ai.render import render_image
from template_ai.importer import import_file
from template_ai.input_graph import InputGraph
from template_ai.customers import CustomerStore
from template_ai.customer_catalog import CustomerStyleDialog


def capture(root):
    app=QApplication.instance() or QApplication([]);root=Path(root);root.mkdir(parents=True,exist_ok=True);w=MainWindow(root/'catalog-local-data');templates=[]
    people=[dict(name=['Alex Example'],title=['Designer'],phone=['020-000-0100'],email=['alex@example.test'])]
    for version,width,height in [(1,90,54),(2,100,60)]:
        t=demo_template();t.name='Synthetic Example Style';t.version=version;t.width_mm=width;t.height_mm=height
        if templates:t.family_id=templates[0].family_id
        before=copy.deepcopy(t);before.state='published';candidate=generate(before,people,[],{});assert candidate.valid,candidate.issues
        path=root/f'catalog-synthetic-source-v{version}.png';assert render_image(candidate).save(str(path))
        source=w.library.add_source(path,import_file(path,w.library.assets));crop=Rect(0,0,source['width_mm'],source['height_mm']);t.source_id=source['id'];t.artwork=crop
        work=w.library.create_artwork(source['id'],f'Anonymous Source Work {version}',dict(crop=asdict(crop),work_width=width,work_height=height,slots=[asdict(s) for s in t.slots],visual_confirmed=True));t.source_work_id=work['id'];t.source_work_revision=work['revision'];w.library.publish(t);templates.append(t)
    w.refresh_templates();w.tabs.setCurrentIndex(1);w.show();c=w.template_catalog;c.selected_ids={templates[0].id};c.primary_id=templates[0].id;c.rebuild();app.processEvents();assert w.template_stack.currentIndex()==0;assert not w.property_panel.isEnabled();assert w.grab().save(str(root/'catalog-template-icons.png'))
    c.mode.setCurrentIndex(1);app.processEvents();assert w.grab().save(str(root/'catalog-template-list.png'));assert c.selected_ids=={templates[0].id}
    c.open_editor();app.processEvents();assert w.edit_canvas.readonly;assert w.grab().save(str(root/'catalog-explicit-editor.png'));w.return_catalog()
    store=CustomerStore(w.library);g=InputGraph.from_legacy(people,[]);customer=store.create_graph('00123','Synthetic Example Client',g.data,templates[0].id,True);customer=store.link_style(customer,templates[1].id,True);dialog=CustomerStyleDialog(w,customer);dialog.show();ids={e['id'] for e in dialog.catalog.entries};dialog.catalog.selected_ids=ids;dialog.catalog.primary_id=dialog.catalog.entries[0]['id'];dialog.catalog.rebuild()
    end=time.monotonic()+8
    while (dialog.catalog.controller.active is not None or dialog.catalog.controller.queue) and time.monotonic()<end:app.processEvents();QTest.qWait(10)
    assert all(dialog.catalog.source_results[eid]['result']['status']=='VERIFIED_DERIVATIVE' for eid in ids)
    app.processEvents();assert dialog.grab().save(str(root/'catalog-customer-source-preview.png'))
    comparison=dialog.catalog.compare();app.processEvents();assert comparison.grab().save(str(root/'catalog-customer-compare.png'))
    chosen=next(e for e in dialog.catalog.entries if e['template_id']==templates[1].id);dialog.catalog.selected_ids={chosen['id']};dialog.catalog.primary_id=chosen['id'];dialog.catalog.rebuild()
    with patch('template_ai.customer_catalog.QMessageBox.question',return_value=QMessageBox.Yes):dialog.catalog.pick()
    assert dialog.adopted and w.reorder_template_id==templates[1].id and w.out_w.value()==100;assert store.get(customer['id'])==customer
    comparison.close();dialog.hide();w.tabs.setCurrentIndex(2);app.processEvents();assert w.grab().save(str(root/'catalog-customer-prefilled.png'))
    audit=dict(schema_version=1,evidence_kind='ACTUAL_QT_CATALOG_SOURCE_COMPARE_EXACT_REORDER',anonymous_synthetic_only=True,actual_template_versions=2,actual_sizes_mm=[[90,54],[100,60]],views_preserve_same_selected_id=True,default_browse_does_not_enter_editor=True,explicit_editor_published_readonly=True,source_derivative_hashes_verified=True,source_preview_not_visual_or_print_certification=True,same_customer_only=True,exact_version_and_size_prefilled=True,master_unchanged=True,formal_output_still_disabled=not w.export_button.isEnabled(),raw_source_files_and_databases_exported=False)
    (root/'catalog-gui-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');dialog.catalog.close_previews();w.template_catalog.close_previews();w.pool.waitForDone(6000);app.processEvents();w.input_timer.stop();w.library.db.close();w.hide();print(json.dumps(audit))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--artifacts-dir',required=True);capture(p.parse_args().artifacts_dir)
