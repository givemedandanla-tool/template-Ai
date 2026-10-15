"""待審 Logo 的真實數位檔 proof：只驗編碼／尺寸，不核准商標或實體印刷。"""
from pathlib import Path
import tempfile
from PySide6.QtCore import QMarginsF,QRectF,QSizeF,Qt
from PySide6.QtGui import QImage,QPageLayout,QPageSize,QPainter,QPdfWriter
from PySide6.QtPdf import QPdfDocument
from .background import file_digest
from .logo_assets import errors,geometry
from .model import Rect
from .render import draw_logo


def validate_encoded(path,width,height,dpi=300):
    path=Path(path)
    if path.suffix.lower()=='.pdf':
        document=QPdfDocument()
        try:
            if document.load(str(path))!=QPdfDocument.Error.None_ or document.pageCount()!=1:raise ValueError('PDF無法讀回單頁')
            size=document.pagePointSize(0)
            if abs(size.width()*25.4/72-width)>.05 or abs(size.height()*25.4/72-height)>.05:raise ValueError('PDF物理尺寸不符')
            if document.render(0,document.pagePointSize(0).toSize()).isNull():raise ValueError('PDF頁面無法實際渲染')
        finally:document.close()
    else:
        image=QImage(str(path))
        if image.isNull() or (image.width(),image.height())!=(max(1,round(width*dpi/25.4)),max(1,round(height*dpi/25.4))):raise ValueError('點陣編碼無法讀回或像素尺寸不符')
    return dict(path=str(path),sha256=file_digest(path),bytes=path.stat().st_size)


def create_proof(asset,width,height,root,dpi=300):
    health=errors(asset,False)
    if health:raise ValueError('；'.join(health))
    if not 72<=dpi<=600 or max(1,round(width*dpi/25.4))*max(1,round(height*dpi/25.4))>24_000_000:raise ValueError('Logo proof超出數位像素預算')
    fit=geometry(asset,Rect(0,0,width,height));root=Path(root);root.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='logo-PREVIEW-',dir=root));files=[]
    try:
        for suffix in ('pdf','png','jpg'):
            target=folder/('logo-PREVIEW.'+suffix)
            if suffix=='pdf':
                device=QPdfWriter(str(target));device.setResolution(dpi);device.setPageSize(QPageSize(QSizeF(width,height),QPageSize.Millimeter))
                device.setPageMargins(QMarginsF(0,0,0,0),QPageLayout.Millimeter);device.setTitle('Logo PREVIEW / 未核准來源品質比較')
            else:
                device=QImage(max(1,round(width*dpi/25.4)),max(1,round(height*dpi/25.4)),QImage.Format_ARGB32_Premultiplied)
                device.fill(Qt.transparent if suffix=='png' else Qt.white)
            painter=QPainter(device)
            if not painter.isActive():raise ValueError('Logo proof繪圖器無法啟動')
            painter.setRenderHint(QPainter.Antialiasing);painter.scale(dpi/25.4,dpi/25.4)
            try:draw_logo(painter,QRectF(0,0,width,height),asset)
            finally:painter.end()
            if suffix=='pdf':
                del device
                from .pdf_geometry import exact_page_box
                exact_page_box(target,width,height)
            elif not device.save(str(target),'PNG' if suffix=='png' else 'JPEG',95):raise ValueError('Logo proof編碼失敗')
            files.append(validate_encoded(target,width,height,dpi))
        if errors(asset,False):raise ValueError('Logo來源在proof途中變更')
        return dict(kind='ACTUAL_DIGITAL_ENCODING_AND_DIMENSION_READBACK',frame_mm=[width,height],dpi=dpi,
            contain=fit,files=files,source_hashes=asset['file_hashes'],physical_print_verified=False,
            independent_visual_fidelity_verified=False)
    except BaseException:
        for path in folder.iterdir():path.unlink()
        folder.rmdir();raise
