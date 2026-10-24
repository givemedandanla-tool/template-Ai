"""Tesseract 本機 OCR 僅補充圖文與身分線索，絕不自動核准／拆字排版。"""
from copy import deepcopy
import csv
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from PySide6.QtCore import QRect
from PySide6.QtGui import QImageReader

from .logo_assets import errors
from .model import Rect
from .ocr_runtime import OcrRuntimeError, resolve_runtime, runtime_report


def capability():
    try:
        selected=resolve_runtime()
    except (OcrRuntimeError, OSError, ValueError) as error:
        reason=str(error) if isinstance(error,OcrRuntimeError) else '本機文字辨識配套不可用；仍可人工標記。'
        return dict(available=False,reason=reason,languages=[],runtime=runtime_report(error=error))
    executable=selected['executable'];data=selected.get('data_dir')
    identity=runtime_report(selected)
    command=[executable]+(['--tessdata-dir',data] if data else [])+['--list-langs']
    try:result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',
                              timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except (OSError,subprocess.TimeoutExpired):
        identity.update(state='UNAVAILABLE',error_code='OCR_EXECUTION_UNAVAILABLE')
        return dict(available=False,reason='本機OCR執行檔不可用／逾時，未假稱已辨識',languages=[],runtime=identity)
    if result.returncode:
        identity.update(state='UNAVAILABLE',error_code='OCR_LANGUAGES_UNAVAILABLE')
        return dict(available=False,reason='本機OCR語言資料不可讀',languages=[],runtime=identity)
    available=[value.strip() for value in result.stdout.splitlines()[1:] if value.strip() in ('eng','chi_tra')]
    if selected['origin']=='BUNDLED' and set(available)!={'eng','chi_tra'}:
        identity.update(state='UNAVAILABLE',error_code='BUNDLED_OCR_LANGUAGES_INVALID')
        return dict(available=False,languages=[],runtime=identity,
                    reason='內附文字辨識未能載入英文與繁體中文；請重新完整解壓，仍可人工標記。')
    if not available:identity.update(state='UNAVAILABLE',error_code='OCR_LANGUAGES_UNAVAILABLE')
    return dict(available=bool(available),executable=executable,data_dir=data,
                languages=available,runtime=identity,
                reason='本機文字線索；非原生可編輯文字或公司身分證明')


def recognize(asset):
    health=errors(asset,False)
    if health:raise ValueError('；'.join(health))
    context=capability()
    if not context['available']:raise ValueError(context['reason'])
    reader=QImageReader(asset['image']);size=reader.size()
    if not size.isValid() or size.width()*size.height()>12_000_000:raise ValueError('OCR圖片超出1200萬像素預算')
    image=reader.read()
    if image.isNull():raise ValueError('OCR來源圖片不可讀')
    width,height=asset['source_width_mm'],asset['source_height_mm']
    crop=Rect(**asset['crop']) if asset.get('crop') else Rect(0,0,width,height)
    left,top=math.floor(crop.x*image.width()/width),math.floor(crop.y*image.height()/height)
    right,bottom=math.ceil((crop.x+crop.w)*image.width()/width),math.ceil((crop.y+crop.h)*image.height()/height)
    region=QRect(left,top,right-left,bottom-top).intersected(image.rect())
    if region.isEmpty():raise ValueError('OCR區域沒有可讀像素')
    environment=os.environ.copy();environment['OMP_THREAD_LIMIT']='1'
    with tempfile.TemporaryDirectory(prefix='template-ai-ocr-') as directory:
        source=Path(directory)/'region.png'
        if not image.copy(region).save(str(source),'PNG'):raise ValueError('OCR暫存失敗')
        command=[context['executable'],str(source),'stdout']
        if context['data_dir']:command+=['--tessdata-dir',context['data_dir']]
        # 自訂語言資料目錄沒有系統 configs/tsv；直接使用官方輸出參數。
        command+=['-l','+'.join(context['languages']),'--psm','11',
                  '-c','tessedit_create_tsv=1','-c','tessedit_create_txt=0']
        result=subprocess.run(command,capture_output=True,text=True,timeout=30,env=environment,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise ValueError('本機OCR處理失敗，未建立身分／核准資料')
    if len(result.stdout.encode())>1_048_576:raise ValueError('OCR文字超出單次metadata預算')
    if not result.stdout.startswith('level\tpage_num\t'):
        raise ValueError('OCR沒有回傳有效TSV結果，未將空輸出假稱辨識成功')
    words=[]
    for row in csv.DictReader(result.stdout.splitlines(),delimiter='\t'):
        text=(row.get('text') or '').strip()
        if not text:continue
        try:
            x,y,w,h=[int(row[key]) for key in ('left','top','width','height')]
            confidence=float(row['conf'])
        except (ValueError,KeyError):continue
        if len(words)>=1000:raise ValueError('OCR線索超過1000筆，請縮小候選區域')
        words.append(dict(text=text[:512],confidence=confidence,
            source_region_mm=dict(x=(region.x()+x)*width/image.width(),y=(region.y()+y)*height/image.height(),
                                  w=w*width/image.width(),h=h*height/image.height())))
    if errors(asset,False):raise ValueError('OCR期間來源已變更，線索不可使用')
    return dict(method='TESSERACT_LOCAL_OCR_CLUES_ONLY',languages=context['languages'],words=words,
        missing_languages=[language for language in ('eng','chi_tra') if language not in context['languages']],
        native_editability='UNKNOWN',company_identity='UNCONFIRMED',
        scope='Hints only; not field truth, logo reconstruction, company merge or publication approval')


def annotate(store,identity,expected_revision):
    candidate=store.proposal(identity)
    if candidate['revision']!=expected_revision or candidate['state'] not in ('PENDING','NEEDS_REPAIR'):
        raise ValueError('候選已更新或已審核，不能附加過期OCR')
    store._fresh(candidate);result=recognize(candidate['asset'])
    store.db.execute('BEGIN IMMEDIATE')
    try:
        current=store.proposal(identity)
        if current['revision']!=expected_revision or current['state']!=candidate['state']:
            raise ValueError('OCR期間候選已變更，沒有覆寫新版')
        store._fresh(current)
        payload={k:deepcopy(v) for k,v in current.items() if k not in ('id','revision','state')}
        payload['evidence']['ocr']=result
        store.db.execute('UPDATE logo_proposals SET revision=revision+1,state=?,payload=? WHERE id=? AND revision=?',
            ('PENDING',json.dumps(payload,ensure_ascii=False),identity,expected_revision))
        store.library.event(identity,'logo_local_ocr_clues_added_not_identity_approval')
        store.db.commit();return store.proposal(identity)
    except BaseException:store.db.rollback();raise
