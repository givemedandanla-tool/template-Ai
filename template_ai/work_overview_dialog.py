"""Paged, source-linked work overview and direct source-coordinate region editor."""
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QSize
from PySide6.QtGui import QImageReader,QImage,QPixmap,QIcon,QPen,QColor
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QListWidget,QMessageBox)
from .gui import Canvas
from .model import Rect
from .training_store import TrainingStore
from .batch_import import healthy_source


class WorkOverviewDialog(QDialog):
    def __init__(self,window,parent=None):
        super().__init__(parent or window);self.window=window;self.store=TrainingStore(window.library);self.offset=0;self.rows=[];self.setWindowTitle('來源／作品總覽：AI候選與確認分開');self.resize(1200,780)
        layout=QVBoxLayout(self);bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('全庫搜尋作品／來源檔名／ID／尺寸，例如90.0x54.0');self.query.textChanged.connect(self.search);bar.addWidget(self.query)
        self.state=QComboBox();self.state.addItems(['ALL','PENDING','CONFIRMED','STALE','SUPERSEDED']);self.state.currentIndexChanged.connect(self.search);bar.addWidget(self.state);layout.addLayout(bar)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status);self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['來源縮圖','作品／來源／頁','物理尺寸／來源裁切','狀態／版次','來源證據']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.setIconSize(QSize(110,70));self.table.cellDoubleClicked.connect(lambda *_:self.edit());layout.addWidget(self.table,1)
        bar=QHBoxLayout()
        for label,fn in [('上一頁',lambda:self.page(-100)),('下一頁',lambda:self.page(100)),('刷新',self.reload),('定位原作品',self.locate),('原作品畫布標記／校正',self.edit)]:button=QPushButton(label);button.clicked.connect(fn);bar.addWidget(button)
        layout.addLayout(bar);self.reload()

    def search(self,*_):self.offset=0;self.reload()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()

    def reload(self):
        try:
            query='%'+self.query.text().strip().casefold()+'%';self.rows=[]
            sql="SELECT a.id FROM artworks a JOIN sources s ON s.id=a.source_id WHERE lower(a.name||' '||a.id||' '||a.source_id||' '||s.original_path||' '||round(json_extract(a.payload,'$.work_width'),1)||'x'||round(json_extract(a.payload,'$.work_height'),1)) LIKE ? ORDER BY a.source_id,a.id LIMIT 100 OFFSET ?"
            for wid, in self.window.library.db.execute(sql,(query,self.offset)):
                work=self.window.library.artwork(wid);state='SUPERSEDED' if work['payload'].get('segmentation_state')=='SUPERSEDED' else self.store.facts_state(wid)
                if self.state.currentText()!='ALL' and self.state.currentText()!=state:continue
                self.rows.append((work,state,self.window.library.source(work['source_id'])))
            self.table.setRowCount(len(self.rows))
            for i,(work,state,source) in enumerate(self.rows):
                payload=work['payload'];icon=QTableWidgetItem('待核對' if not healthy_source(source) else '')
                if not icon.text():
                    reader=QImageReader(source['image']);size=reader.size();size.scale(320,240,Qt.KeepAspectRatio);reader.setScaledSize(size);image=reader.read()
                    if not image.isNull():
                        crop=payload['crop'];rect=QRectF(crop['x']*image.width()/source['width_mm'],crop['y']*image.height()/source['height_mm'],crop['w']*image.width()/source['width_mm'],crop['h']*image.height()/source['height_mm']);icon.setIcon(QIcon(QPixmap.fromImage(image.copy(rect.toAlignedRect()))))
                values=[icon,QTableWidgetItem(work['name']+'\n'+Path(source['current_path']).name+'／頁'+str(source['page'])+'\n'+work['id']),QTableWidgetItem(f"{payload['work_width']:.3f} × {payload['work_height']:.3f} mm\n來源框：{payload['crop']}"),QTableWidgetItem(state+'／r'+str(work['revision'])),QTableWidgetItem('來源幾何候選；需視覺確認\n原生Illustrator圖層對應 UNKNOWN')]
                for j,value in enumerate(values):self.table.setItem(i,j,value)
                self.table.setRowHeight(i,88)
            self.status.setText(f'來源／檔名／尺寸先全庫搜尋；本頁讀取最多100作品，狀態篩選後{len(self.rows)}作品，頁起點{self.offset}。縮圖為衍生來源，不代表AI已確認。')
        except Exception as error:self.status.setText('作品總覽未完成：'+str(error))

    def current(self):
        index=self.table.currentRow()
        if not 0<=index<len(self.rows):raise ValueError('先選明確來源作品')
        work=self.rows[index][0]
        if self.window.library.artwork(work['id'])['revision']!=work['revision']:raise ValueError('作品已更新，先重新核對')
        return work

    def locate(self):
        try:
            from .training_navigation import locate_work
            locate_work(self.window,self.current()['id'],[]);self.status.setText('已定位來源／作品；沒有核准事實。')
        except Exception as error:self.status.setText(str(error))

    def edit(self):
        try:
            from .annotation_dialog import AnnotationDialog
            dialog=AnnotationDialog(self.window,self.current()['id'],self);dialog.exec();dialog.deleteLater();self.reload()
        except Exception as error:self.status.setText('未校正：'+str(error))


class SourceRegionsDialog(QDialog):
    def __init__(self,library,work,parent=None):
        super().__init__(parent);self.source=library.source(work['source_id']);self.regions=[];self.overlays=[];self.resize(1100,800);self.setWindowTitle('在同來源頁畫作品邊界：不改原稿')
        if not healthy_source(self.source):raise ValueError('來源或衍生圖失效，不能假稱可視核對')
        layout=QVBoxLayout(self);self.status=QLabel('橘色是原作品；綠色是新作品候選。可連續畫1～20個區域；既有欄位須完整且唯一歸入新區域。');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.canvas=Canvas();reader=QImageReader(self.source['image']);size=reader.size();size.scale(1600,1200,Qt.KeepAspectRatio);reader.setScaledSize(size);image=reader.read()
        if image.isNull():raise ValueError('來源圖不可讀')
        self.canvas.set_content(self.source['width_mm'],self.source['height_mm'],image,crop=Rect(**work['payload']['crop']));self.canvas.set_mode('crop');self.canvas.rectangle.connect(self.add);layout.addWidget(self.canvas,1)
        self.list=QListWidget();self.list.setMaximumHeight(130);layout.addWidget(self.list);bar=QHBoxLayout()
        for label,fn in [('畫作品邊界',lambda:self.canvas.set_mode('crop')),('只平移視角',lambda:self.canvas.set_mode('pan')),('撤回最後一框',self.undo),('使用原作品框',lambda:self.add(Rect(**work['payload']['crop']))),('核對所畫區域',self.accept),('取消',self.reject)]:button=QPushButton(label);button.clicked.connect(fn);bar.addWidget(button)
        layout.addLayout(bar)

    def showEvent(self,event):super().showEvent(event);self.canvas.fit()

    def add(self,rect):
        if len(self.regions)>=20 or not rect.inside(self.source['width_mm'],self.source['height_mm']):self.status.setText('區域須位於本來源頁，且最多20框');return
        self.regions.append(rect);pen=QPen(QColor('#059669'),2,Qt.DashLine);pen.setCosmetic(True);self.overlays.append(self.canvas.scene().addRect(QRectF(rect.x,rect.y,rect.w,rect.h),pen));self.list.addItem(f'x={rect.x:.3f}, y={rect.y:.3f}, w={rect.w:.3f}, h={rect.h:.3f} mm')

    def undo(self):
        if self.regions:self.regions.pop();self.canvas.scene().removeItem(self.overlays.pop());self.list.takeItem(self.list.count()-1)

    def accept(self):
        if not self.regions:self.status.setText('先在來源畫出明確作品區域');return
        super().accept()
