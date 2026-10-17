"""One read-only index, two views, and explicit edit/reorder actions."""
from copy import deepcopy
import sqlite3
from PySide6.QtCore import Qt,QSize,QItemSelectionModel,QEvent
from PySide6.QtGui import QIcon,QPixmap
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QLineEdit,QComboBox,QLabel,
    QPushButton,QTreeWidget,QTreeWidgetItem,QListWidget,QListWidgetItem,QAbstractItemView,QPlainTextEdit,
    QDialog,QDialogButtonBox,QSizePolicy)
from . import catalog
from .catalog_preview import PreviewController


class CatalogWidget(QWidget):
    def __init__(self,window,customer=None,on_pick=None,allow_edit=True):
        super().__init__(window);self.window=window;self.customer=deepcopy(customer);self.on_pick=on_pick;self.allow_edit=allow_edit
        self.entries=[];self.visible=[];self.byid={};self.selected_ids=set();self.primary_id=None;self.page=0;self.blocked=False;self.closed=False;self.source_results={};self.compare_dialogs=[];self.preview_pixmap=None
        self.controller=PreviewController(window,self);self.controller.result.connect(self.preview_done)
        layout=QVBoxLayout(self)
        bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('搜尋模板名稱／ID／版次／來源ID');bar.addWidget(self.query)
        self.state=QComboBox()
        for label,value in [('全部狀態',None),('已發布','published'),('草稿','draft'),('未知','UNKNOWN')]:self.state.addItem(label,value)
        bar.addWidget(self.state);self.version=QComboBox();bar.addWidget(self.version)
        self.mode=QComboBox();self.mode.addItems(['縮圖瀏覽','詳細列表']);bar.addWidget(self.mode)
        self.refresh_button=self.button(bar,'重新整理',self.reload)
        if allow_edit:
            self.button(bar,'新增空白矩形模板',window.new_template);self.button(bar,'加入合成示範模板',window.add_demo)
        layout.addLayout(bar)
        split=QSplitter();self.tree=QTreeWidget();self.tree.setHeaderLabels(['實體尺寸 → 人物容量']);split.addWidget(self.tree)
        self.items=QListWidget();self.items.setSelectionMode(QAbstractItemView.ExtendedSelection);self.items.setResizeMode(QListWidget.Adjust);split.addWidget(self.items)
        detail=QWidget();v=QVBoxLayout(detail);self.picture=QLabel('請選擇一個模板，瀏覽不進入編輯');self.picture.setTextFormat(Qt.PlainText);self.picture.setAlignment(Qt.AlignCenter);self.picture.setMinimumSize(240,150);self.picture.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);self.picture.installEventFilter(self);v.addWidget(self.picture)
        self.preview_state=QLabel('來源縮圖 UNKNOWN');self.preview_state.setTextFormat(Qt.PlainText);self.preview_state.setWordWrap(True);v.addWidget(self.preview_state)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);v.addWidget(self.details,1);split.addWidget(detail);split.setSizes([190,610,320]);layout.addWidget(split,1)
        bar=QHBoxLayout();self.previous=self.button(bar,'上一頁',lambda:self.change_page(-1));self.next=self.button(bar,'下一頁',lambda:self.change_page(1));self.button(bar,'清除全部選取',self.clear_selection);self.button(bar,'並排比較選中兩版',self.compare)
        if allow_edit:self.edit_button=self.button(bar,'明確開啟模板編輯區',self.open_editor)
        else:self.edit_button=None
        if on_pick:self.pick_button=self.button(bar,'沿用選中exact版型（先確認）',self.pick)
        else:self.pick_button=None
        layout.addLayout(bar);self.status=QLabel();self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        self.query.textChanged.connect(self.filter_changed);self.state.currentIndexChanged.connect(self.filter_changed);self.version.currentIndexChanged.connect(self.filter_changed);self.mode.currentIndexChanged.connect(self.change_view);self.tree.currentItemChanged.connect(self.filter_changed)
        self.items.itemSelectionChanged.connect(self.selection_changed);self.items.currentItemChanged.connect(self.current_changed)
        self.reload()

    def button(self,row,text,fn):
        b=QPushButton(text);b.clicked.connect(fn);row.addWidget(b);return b

    def reload(self):
        if self.closed:return
        try:
            if self.customer is None:
                from .startup_catalog import facets
                index=facets(self.window.library);self.partial_facets=index['partial_facets'];tree=index['tree'];versions=index['versions']
                keep=self.selected_ids|({self.primary_id} if self.primary_id else set())
                ids=[identity for identity in keep if self.window.library.db.execute('SELECT 1 FROM templates WHERE id=?',(identity,)).fetchone()]
                self.entries=catalog.rows(self.window.library,template_ids=ids);self.byid={r['id']:r for r in self.entries}
            else:
                self.entries=catalog.rows(self.window.library,self.customer);self.byid={r['id']:r for r in self.entries};tree=catalog.hierarchy(self.entries);versions=sorted({r['version'] for r in self.entries if r['version'] is not None})
            self.source_results={k:v for k,v in self.source_results.items() if k in self.byid and v['signature']==self.byid[k]['signature'] and self.cache_current(v)}
            gone=self.selected_ids-self.byid.keys();self.selected_ids.intersection_update(self.byid)
            if self.primary_id not in self.byid:self.primary_id=None
            old_version=self.version.currentData();self.version.blockSignals(True);self.version.clear();self.version.addItem('全部版次',None)
            for version in versions:self.version.addItem('v'+str(version),version)
            self.version.setCurrentIndex(max(0,self.version.findData(old_version)));self.version.blockSignals(False)
            previous=self.tree.currentItem();key=previous.data(0,Qt.UserRole) if previous else None
            self.tree.blockSignals(True);self.tree.clear();root=QTreeWidgetItem(['全部尺寸／容量']);root.setData(0,Qt.UserRole,None);self.tree.addTopLevelItem(root);selected=root
            for size,caps in tree.items():
                item=QTreeWidgetItem([f'{size[0]:g} × {size[1]:g} mm']);item.setData(0,Qt.UserRole,dict(size=list(size),capacity=None));self.tree.addTopLevelItem(item)
                if key==item.data(0,Qt.UserRole):selected=item
                for capacity,count in sorted(caps.items(),key=lambda x:x[0] or 0):
                    child=QTreeWidgetItem([f"{capacity if capacity is not None else 'UNKNOWN'} 人 · {count}版本"]);child.setData(0,Qt.UserRole,dict(size=list(size),capacity=capacity));item.addChild(child)
                    if key==child.data(0,Qt.UserRole):selected=child
            self.tree.setCurrentItem(selected);self.tree.expandAll();self.tree.blockSignals(False)
            self.page=0;self.rebuild()
            if gone:self.status.setText(self.status.text()+f'；{len(gone)}個原選取已失聯，未替換版本')
        except (ValueError,KeyError,TypeError,sqlite3.DatabaseError) as error:self.status.setText('目錄未完成：'+str(error))

    def filter_changed(self,*args):
        if self.blocked:return
        self.page=0;self.rebuild()

    def change_page(self,delta):
        self.page=max(0,self.page+delta);self.rebuild()

    def matching(self):
        current=self.tree.currentItem();key=current.data(0,Qt.UserRole) if current else None
        return catalog.filtered(self.entries,self.query.text(),key.get('size') if key else None,key.get('capacity') if key else None,self.state.currentData(),self.version.currentData())

    def rebuild(self):
        self.blocked=True;self.items.blockSignals(True)
        try:
            if self.customer is None:
                from .startup_catalog import search
                current=self.tree.currentItem();key=current.data(0,Qt.UserRole) if current else None
                result=search(self.window.library,self.query.text(),key.get('size') if key else None,key.get('capacity') if key else None,self.state.currentData(),self.version.currentData(),self.page)
                self.page=result['page'];self.matching_count=result['total'];self.visible=catalog.rows(self.window.library,template_ids=result['ids']);self.entries=self.visible
                keep=self.selected_ids|({self.primary_id} if self.primary_id else set());self.byid={identity:row for identity,row in self.byid.items() if identity in keep};self.byid.update({row['id']:row for row in self.visible});count=self.matching_count
            else:
                matching=self.matching();count=len(matching);self.page=min(self.page,max(0,(count-1)//catalog.PAGE_SIZE));self.visible=matching[self.page*catalog.PAGE_SIZE:(self.page+1)*catalog.PAGE_SIZE]
            self.items.clear()
            for row in self.visible:
                state=row['state']+'／'+row['reference_state'];text=f"{row['name']} · v{row['version'] if row['version'] is not None else 'UNKNOWN'}\n{row['width']:g}×{row['height']:g} mm · 容量 {row['capacity']}人\n{state}\n{row['template_id']}"
                item=QListWidgetItem(text);item.setData(Qt.UserRole,row['id']);item.setToolTip(text+'\n'+('來源縮圖待核對／UNKNOWN' if self.customer else '實際模板框位示意，非原稿縮圖／非新排版'))
                if not self.customer:item.setIcon(QIcon(QPixmap.fromImage(catalog.frame_diagram(row))))
                elif self.current_message(row['id']):self.set_source_icon(item,self.current_message(row['id']))
                self.items.addItem(item);item.setSelected(row['id'] in self.selected_ids)
                if row['id']==self.primary_id:self.items.setCurrentItem(item,QItemSelectionModel.NoUpdate)
            self.previous.setEnabled(self.page>0);self.next.setEnabled((self.page+1)*catalog.PAGE_SIZE<count);self.change_view();self.update_status(count)
            self.controller.reset(self.visible if self.customer else [])
            if self.primary_id in self.byid:self.show_primary()
        except (ValueError,KeyError,TypeError,sqlite3.Error) as error:
            self.status.setText('目錄未完成，請修正篩選或從診斷核對：'+str(error));self.previous.setEnabled(False);self.next.setEnabled(False)
        finally:self.items.blockSignals(False);self.blocked=False

    def change_view(self,*args):
        icon=self.mode.currentIndex()==0;self.items.setViewMode(QListWidget.IconMode if icon else QListWidget.ListMode);self.items.setIconSize(QSize(216,135) if icon else QSize(88,55));self.items.setGridSize(QSize(254,242) if icon else QSize());self.items.setWordWrap(True)

    def selection_changed(self):
        if self.blocked:return
        visible={r['id'] for r in self.visible};self.selected_ids.difference_update(visible);self.selected_ids.update(i.data(Qt.UserRole) for i in self.items.selectedItems());self.update_status(len(self.matching()))

    def current_changed(self,item,previous=None):
        if self.blocked or not item:return
        self.primary_id=item.data(Qt.UserRole);self.show_primary()

    def show_primary(self):
        if self.primary_id not in self.byid:return
        entry=self.byid[self.primary_id];self.details.setPlainText(catalog.metadata(self.window.library,entry))
        if not self.customer:
            self.set_preview_image(catalog.frame_diagram(entry));self.preview_state.setText('實際模板框位示意；不是原稿／新排版／品質證明')
        else:self.set_preview_image(None);self.picture.setText('來源縮圖讀取中／UNKNOWN')
        if self.current_message(entry['id']):self.display_result(entry['id'],self.current_message(entry['id']))
        self.controller.prioritize(entry)

    def set_source_icon(self,item,message):
        result=message['result']
        if result.get('image') is not None:item.setIcon(QIcon(QPixmap.fromImage(result['image'])))
        else:item.setIcon(QIcon())
        item.setToolTip(item.toolTip()+'\n'+result['status']+'：'+result['reason'])

    def preview_done(self,message):
        if self.closed:return
        row=self.byid.get(message['id'])
        if not row or row['signature']!=message['signature']:return
        result=message['result']
        try:
            if row['template']:
                current=self.window.library.object_snapshot('TEMPLATE',row['template_id'])['payload']
                if catalog.digest(current)!=catalog.digest(row['template']):raise ValueError('版型已變')
            from .source_links import check_verified
            for proof in result.get('proofs',[]):check_verified(proof,proof.hash)
            if row['template']:
                from .model import Template
                self.window.library._template_provenance(Template.from_dict(row['template']))
        except (ValueError,OSError,sqlite3.DatabaseError):message={**message,'result':dict(status='STALE',reason='預覽期間依賴已變，重新整理後再核對',image=None,proofs=[])}
        self.source_results[message['id']]=message
        if len(self.source_results)>96:
            oldest=next(k for k in self.source_results if k!=self.primary_id);self.source_results.pop(oldest)
        if self.customer:
            for i in range(self.items.count()):
                item=self.items.item(i)
                if item.data(Qt.UserRole)==message['id']:self.set_source_icon(item,message)
        if self.primary_id==message['id']:self.display_result(message['id'],message)
        for dialog,ids in list(self.compare_dialogs):
            if dialog.isVisible() and message['id'] in ids:self.fill_compare(dialog,ids)

    def current_message(self,eid):
        message=self.source_results.get(eid);entry=self.byid.get(eid)
        if not message or not entry or message['signature']!=entry['signature'] or not self.cache_current(message):return None
        return message

    def cache_current(self,message):
        try:
            from .source_links import check_verified
            for proof in message['result'].get('proofs',[]):check_verified(proof,proof.hash)
            return True
        except (OSError,ValueError):return False

    def set_preview_image(self,image):
        self.preview_pixmap=QPixmap.fromImage(image) if image is not None else None
        if self.preview_pixmap is None:self.picture.clear()
        else:self.fit_preview(force=True)

    def fit_preview(self,force=False):
        if self.preview_pixmap is None:return
        rect=self.picture.contentsRect();size=QSize(max(1,min(320,rect.width())),max(1,min(210,rect.height())))
        fitted=self.preview_pixmap.scaled(size,Qt.KeepAspectRatio,Qt.SmoothTransformation)
        current=self.picture.pixmap()
        if force or current.isNull() or current.size()!=fitted.size():self.picture.setPixmap(fitted)

    def eventFilter(self,watched,event):
        if watched is self.picture and event.type()==QEvent.Resize:self.fit_preview()
        return super().eventFilter(watched,event)

    def display_result(self,eid,message):
        result=message['result'];image=result.get('image')
        if image is not None:self.set_preview_image(image)
        elif self.customer:self.set_preview_image(None);self.picture.setText('來源縮圖 '+result['status'])
        self.preview_state.setText(('模板框位示意（非原稿）；' if not self.customer and image is None else '')+result['status']+'：'+result['reason'])

    def update_status(self,count):
        if self.customer is None:count=getattr(self,'matching_count',0)
        hidden=len(self.selected_ids-{r['id'] for r in getattr(self,'visible',[])})
        self.status.setText(f'符合{count}版本／第{self.page+1}頁；已選{len(self.selected_ids)}（其中{hidden}不在本頁，仍保留）；瀏覽／切換不保存、不發布、不採用。')
        if getattr(self,'partial_facets',False):self.status.setText(self.status.text()+' 尺寸／版次樹顯示前200組；搜尋及分頁涵蓋全部。')
        if self.edit_button:self.edit_button.setEnabled(len(self.selected_ids)==1 and not self.window.busy)
        if self.pick_button:self.pick_button.setEnabled(len(self.selected_ids)==1 and not self.window.busy)

    def clear_selection(self):
        self.selected_ids.clear();self.primary_id=None;self.picture.clear();self.details.clear();self.preview_state.setText('未選取模板／來源縮圖 UNKNOWN');self.rebuild()

    def choose_exact(self):
        if len(self.selected_ids)!=1:raise ValueError('請明確選一個版本；未自動取最新或排除隱藏選取')
        row=self.byid[next(iter(self.selected_ids))]
        if not row['template'] or row['reference_state']!='CURRENT':raise ValueError('版型失聯／引用已變，不能替換為其他版本')
        current=self.window.library.object_snapshot('TEMPLATE',row['template_id'])['payload']
        if catalog.digest(current)!=catalog.digest(row['template']):raise ValueError('版型已更新；請重新整理與確認')
        return row

    def open_editor(self):
        try:
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window);row=self.choose_exact();self.window.open_catalog_editor(row['template_id'])
        except (ValueError,KeyError,sqlite3.DatabaseError) as error:self.status.setText('未進入編輯：'+str(error))

    def pick(self):
        try:self.on_pick(self.choose_exact())
        except (ValueError,KeyError,sqlite3.DatabaseError) as error:self.status.setText('未沿用：'+str(error))

    def compare(self):
        ids=[r['id'] for r in self.entries if r['id'] in self.selected_ids]
        if len(ids)!=2:self.status.setText('請明確選兩個版本並排比較；未擅自縮小多選範圍');return
        dialog=QDialog(self);dialog.setWindowTitle('兩個確切版型：唯讀並排比較／各尺寸獨立');dialog.resize(1060,700);layout=QVBoxLayout(dialog);row=QHBoxLayout();dialog.columns=[]
        for eid in ids:
            column=QWidget();v=QVBoxLayout(column);image=QLabel();image.setTextFormat(Qt.PlainText);image.setMinimumHeight(180);v.addWidget(image);text=QPlainTextEdit();text.setReadOnly(True);v.addWidget(text);dialog.columns.append((image,text));row.addWidget(column)
        layout.addLayout(row);buttons=QDialogButtonBox(QDialogButtonBox.Close);buttons.rejected.connect(dialog.reject);buttons.button(QDialogButtonBox.Close).setText('關閉');layout.addWidget(buttons);self.compare_dialogs.append((dialog,ids));self.fill_compare(dialog,ids);dialog.show()
        for eid in ids:self.controller.prioritize(self.byid[eid])
        return dialog

    def fill_compare(self,dialog,ids):
        for eid,(picture,text) in zip(ids,dialog.columns):
            row=self.byid.get(eid)
            if not row:picture.setText('版本失聯');continue
            result=(self.current_message(eid) or {}).get('result',{});image=result.get('image')
            if image is not None:picture.setPixmap(QPixmap.fromImage(image))
            elif self.customer:picture.clear();picture.setText('原稿預覽 '+result.get('status','UNKNOWN'))
            else:picture.setPixmap(QPixmap.fromImage(catalog.frame_diagram(row)))
            text.setPlainText(catalog.metadata(self.window.library,row)+'\n\n來源圖：'+result.get('status','UNKNOWN')+'\n'+result.get('reason','沒有來源證據時不編造縮圖')+'\n\n'+catalog.geometry_description(row))

    def close_previews(self):
        self.closed=True;self.controller.close()
        for d,ids in self.compare_dialogs:d.close()
