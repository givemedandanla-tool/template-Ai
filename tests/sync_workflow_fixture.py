"""Authored two-person/two-company, three-candidate/two-size native fixture."""
import tempfile,copy
from pathlib import Path
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from template_ai.gui import MainWindow
from template_ai.input_graph import InputGraph
from template_ai.logo_store import LogoStore
from template_ai.importer import import_file
from template_ai.model import Template,Slot,Rect
from template_ai.multi_size_dialog import MultiSizeDialog
from template_ai.multi_size_edit import SizeEditAdapter,SizeEditController
from gui_wait import wait_for_gui
from runtime_fixture import controlled_resources
APP=QApplication.instance() or QApplication([])
REVIEW=dict(identity_confirmed=True,whole_mark_confirmed=True,usage_authorized=True,digital_quality_confirmed=True,actor='SYNTHETIC_AUTHORED_FIXTURE',note='Authored geometric mark and exact company/digital review; no private artwork')


class SyncWorkflowFixture:
    def __init__(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.w=MainWindow(self.root/'data');controlled_resources(self.w);self.store=LogoStore(self.w.library);self.assets={};self.registry=[];self.payloads=[]
        for index,(name,color) in enumerate((('Synthetic Alpha','#df3030'),('Synthetic Beta','#3060df'))):
            company=self.store.create_company(name,'Authored synthetic identity '+str(index),True);self.registry.append(company);path=self.root/('authored-mark-'+str(index)+'.svg');path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm"><rect width="20" height="10" fill="'+color+'"/></svg>');image=import_file(path,self.w.library.assets);payload=dict(image=image['image'],svg=image['svg'],source_width_mm=image['width_mm'],source_height_mm=image['height_mm'],crop=None);self.payloads.append(payload)
            for width,height in ((90,54),(100,60)):
                if index==1 and width==100:continue
                plan=self.store.propose(payload,width,height,company_id=company['id']);self.assets[index,width]=self.store.approve(plan['id'],plan['revision'],company['id'],REVIEW,True)
        graph=InputGraph.from_legacy([dict(name=['Alex Example'],phone=['+12025550100'],company='c1'),dict(name=['Blair Example'],phone=['+12025550100'],company='c2')],[dict(name=c['name']) for c in self.registry],dict(c1=self.assets[0,90],c2=self.assets[1,90]))
        for index,company in enumerate(graph.data['companies']):self.store.bind(company['id'],self.registry[index]['id'],self.registry[index]['name'],True)
        self.w.adopt_input_graph(graph.data,history=graph);self.templates={}
        for name,width,height,x,logo_x in (('A90',90,54,3,62),('B90',90,54,5,62),('C100',100,60,6,72)):
            slots=[Slot('name','p1',Rect(x,3,44,11),size_pt=18),Slot('phone','p1',Rect(x,16,44,6),size_pt=10),Slot('name','p2',Rect(x,28,44,11),size_pt=18),Slot('phone','p2',Rect(x,41,44,6),size_pt=10),Slot('logo','c1',Rect(logo_x,3,20,12)),Slot('logo','c2',Rect(logo_x,30,20,12)),Slot('company','c1',Rect(logo_x-5,17,30,6),size_pt=10),Slot('company','c2',Rect(logo_x-5,44,30,6),size_pt=10)];template=Template('Synthetic '+name,width,height,slots,capacity=2,company_bindings=dict(p1='c1',p2='c2'));self.w.library.publish(template);self.templates[name]=template
        self.d=MultiSizeDialog(self.w);self.d.show()
        for row in range(self.d.table.rowCount()):self.d.table.item(row,0).setCheckState(Qt.Checked)
        self.d.start();self.wait();self.select('A90')
    def wait(self):
        if not wait_for_gui(lambda:not self.d.running and not self.w.busy,10):raise AssertionError('Owned synthetic synchronization workflow did not complete')
    def entry(self,name):return next(e for e in self.d.service.entries if self.templates[name].id in {c.template.id for c in e['candidates']})
    def candidate(self,name):return next(c for c in self.entry(name)['candidates'] if c.template.id==self.templates[name].id)
    def select(self,name):
        entry=self.entry(name);row=next(i for i,s in enumerate(self.d.sizes) if s==entry['size_mm']);self.d.table.setCurrentCell(row,1);self.d.select_candidate(entry['key'],self.templates[name].id)
    def adapter(self,name):
        entry=self.entry(name);index=next(i for i,c in enumerate(entry['candidates']) if c.template.id==self.templates[name].id);return SizeEditAdapter(self.d,entry,index),index
    def controller(self,name):
        adapter,index=self.adapter(name);return adapter,index,SizeEditController(adapter)
    def change_phone(self,value):
        graph=self.w.active_input_graph.clone();entity=graph.data['people'][0]['id'];field=next(f for f in graph.data['fields'] if f['owner_id']==entity and f['kind']=='phone');graph.apply(graph.preview('edit_field',field_id=field['id'],value=value),True);self.w.adopt_input_graph(graph.data,history=graph);return field['id']
    def sync(self):self.d.sync_source();self.wait()
    def close(self):
        self.d.stop.set();self.w.input_timer.stop();self.w.execution_queue.cancel_event.set();self.w.pool.waitForDone(5000);APP.processEvents();self.d.deleteLater();self.w.font_manager.close();self.w.library.close();self.w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);self.tmp.cleanup()
