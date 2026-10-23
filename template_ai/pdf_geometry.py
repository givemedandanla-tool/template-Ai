"""Qt 6.8將MediaBox量化到整點；以pypdf設定精確mm盒，不縮放或重繪內容。"""
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader,PdfWriter
from pypdf.generic import RectangleObject


def exact_page_box(path,width_mm,height_mm):
    path=Path(path);reader=PdfReader(BytesIO(path.read_bytes()));writer=PdfWriter(clone_from=reader)
    if len(writer.pages)!=1:raise ValueError('數位輸出應為單頁，不能猜測頁面尺寸')
    box=RectangleObject([0,0,width_mm*72/25.4,height_mm*72/25.4])
    page=writer.pages[0];page.mediabox=box;page.cropbox=RectangleObject(box)
    with path.open('wb') as stream:writer.write(stream)
