"""Bounded, actual Tesseract inference with immutable local language models."""
import copy
import csv
import io
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict
from collections import Counter,defaultdict
from PySide6.QtGui import QImageReader
from .background import file_digest
from .training_store import digest
from .model import Rect,Slot

VERSION='quality-source-ocr-1'


def configuration(config):
    if config is None:return None
    if not isinstance(config,dict) or set(config)!={'languages','psm'}:raise ValueError('OCR需明列本機語言與頁面分割模式')
    langs=config['languages']
    if not isinstance(langs,list) or not 1<=len(langs)<=2 or len(set(langs))!=len(langs) or not set(langs)<={'eng','chi_tra'}:raise ValueError('OCR只能選實際支援eng／chi_tra語言，不能用模型名稱標籤冒充')
    if type(config['psm']) is not int or config['psm'] not in (6,11):raise ValueError('OCR分割模式需明確單塊文字6或稀疏文字11')
    return copy.deepcopy(config)


def runtime(executable):
    path=Path(executable).resolve()
    if not path.is_file():raise ValueError('實際Tesseract執行檔不存在')
    result=subprocess.run([str(path),'--version'],capture_output=True,text=True,timeout=10)
    if result.returncode:raise ValueError('Tesseract實際版本讀取失敗')
    return dict(executable=str(path),sha256=file_digest(path),version=result.stdout[:2000])


def freeze(assets,config):
    config=configuration(config)
    if config is None:return None
    from .logo_ocr import capability
    cap=capability()
    if not cap['available'] or not set(config['languages'])<=set(cap['languages']) or not cap.get('data_dir'):raise ValueError('缺少所選實際本機OCR語言資料，未安裝／冒充可執行模型')
    models=[];total=0
    for language in config['languages']:
        source=Path(cap['data_dir'])/(language+'.traineddata')
        if source.is_symlink() or not source.is_file():raise ValueError('OCR語言模型失聯或符號連結')
        size=source.stat().st_size;total+=size
        if not 0<size<=128*1048576 or total>256*1048576:raise ValueError('OCR模型超過本機128MiB／總256MiB預算')
        models.append(dict(language=language,sha256=file_digest(source),bytes=size,source=source))
    identity=digest([{key:value for key,value in model.items() if key!='source'} for model in models]);target=Path(assets)/'quality-ocr'/identity;target.mkdir(parents=True,exist_ok=True)
    frozen=[]
    for model in models:
        destination=target/(model['language']+'.traineddata')
        if not destination.exists():
            fd,temporary=tempfile.mkstemp(prefix='model-',dir=target);os.close(fd)
            try:
                shutil.copyfile(model['source'],temporary)
                if file_digest(temporary)!=model['sha256'] or file_digest(model['source'])!=model['sha256']:raise ValueError('OCR模型快照期間來源已變更')
                os.replace(temporary,destination)
            finally:
                if Path(temporary).exists():Path(temporary).unlink()
        frozen.append(dict(language=model['language'],sha256=model['sha256'],bytes=model['bytes'],path=str(destination)))
    record=dict(algorithm_version=VERSION,configuration=config,runtime=runtime(cap['executable']),models=frozen,local_only=True,raw_text_confidence_filter=False)
    verify(record);return record


def verify(record):
    if record is None:return
    configuration(record['configuration'])
    if record['algorithm_version']!=VERSION or runtime(record['runtime']['executable'])!=record['runtime']:raise ValueError('OCR實際執行器／口徑版本已變更，不能冒稱舊版A/B')
    if [model['language'] for model in record['models']]!=record['configuration']['languages']:raise ValueError('OCR語言模型與固定順序不一致')
    roots=set()
    for model in record['models']:
        path=Path(model['path']);roots.add(path.parent)
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=model['bytes'] or file_digest(path)!=model['sha256']:raise ValueError('已固定OCR語言模型失聯／指紋已改變')
    if len(roots)!=1:raise ValueError('OCR模型目錄不一致')


def parse_tsv(raw,pixel_width,pixel_height,width_mm,height_mm):
    if len(raw.encode())>1048576 or not raw.startswith('level\tpage_num\t'):raise ValueError('OCR未回傳完整有界TSV，不能當空辨識成功')
    groups=defaultdict(list);seen=set();words=0
    for row in csv.DictReader(io.StringIO(raw),delimiter='\t'):
        value=(row.get('text') or '').strip()
        if not value:continue
        try:
            level=int(row['level']);x,y,w,h=[int(row[key]) for key in ('left','top','width','height')]
            confidence=float(row['conf']);key=tuple(int(row[k]) for k in ('page_num','block_num','par_num','line_num'));word=int(row['word_num'])
        except (ValueError,KeyError,TypeError) as error:raise ValueError('OCR非空文字列座標／信心／分組失效，未靜默省略') from error
        if level!=5 or not math.isfinite(confidence) or min(x,y)<0 or min(w,h)<=0 or x+w>pixel_width or y+h>pixel_height or (key,word) in seen:raise ValueError('OCR非空字框失效／重複／越界，未排除分母')
        seen.add((key,word));words+=1
        if words>1000 or len(value)>2048:raise ValueError('OCR超過1000字詞／單詞2048字預算，未截斷冒充完整')
        groups[key].append(dict(order=word,text=value,x=x,y=y,w=w,h=h,confidence=confidence))
    if len(groups)>200:raise ValueError('OCR超過200文字行，需受控縮小來源範圍，未刪除來源分母')
    result=[]
    for key,values in sorted(groups.items()):
        values.sort(key=lambda v:v['order']);text=' '.join(v['text'] for v in values)
        if len(text)>2048:raise ValueError('OCR整行文字超過2048字，未截斷')
        left=min(v['x'] for v in values);top=min(v['y'] for v in values);right=max(v['x']+v['w'] for v in values);bottom=max(v['y']+v['h'] for v in values)
        result.append(dict(key=list(key),text=text,rect=dict(x=left*width_mm/pixel_width,y=top*height_mm/pixel_height,w=(right-left)*width_mm/pixel_width,h=(bottom-top)*height_mm/pixel_height),word_confidences=[v['confidence'] for v in values],words=len(values)))
    return result


def lines(source,record):
    verify(record);reader=QImageReader(source['image']);size=reader.size()
    if not size.isValid() or size.width()*size.height()>12_000_000:raise ValueError('OCR來源超過1200萬像素或不可讀，仍保留來源分母')
    from .runtime_worker import stop_tree
    environment=os.environ.copy();environment['OMP_THREAD_LIMIT']='1'
    command=[record['runtime']['executable'],source['image'],'stdout','--tessdata-dir',str(Path(record['models'][0]['path']).parent),'-l','+'.join(record['configuration']['languages']),'--psm',str(record['configuration']['psm']),'-c','tessedit_create_tsv=1','-c','tessedit_create_txt=0']
    with tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as errors:
        process=subprocess.Popen(command,stdout=output,stderr=errors,env=environment,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));start=time.monotonic()
        try:
            while process.poll() is None:
                if time.monotonic()-start>30 or os.fstat(output.fileno()).st_size>1048576 or os.fstat(errors.fileno()).st_size>65536:
                    stop_tree(process);raise ValueError('OCR超時／輸出超限，已停止owned程序，未假稱空解析成功')
                try:process.wait(timeout=.1)
                except subprocess.TimeoutExpired:pass
            output.seek(0);raw=output.read(1048577)
            if process.returncode or len(raw)>1048576:raise ValueError('本機OCR失敗／輸出超限，未刪除來源分母')
        finally:
            if process.poll() is None:stop_tree(process)
            process.wait()
    verify(record)
    return parse_tsv(raw.decode('utf-8','strict'),size.width(),size.height(),source['width_mm'],source['height_mm'])


def analyse(source,assets,model,context,record,vector_analyser):
    from .source_analysis import contains
    from .semantic_fields import recognize
    text_lines=lines(source,record)
    if source.get('svg'):works=vector_analyser(source,assets,model,context)
    else:
        crop=dict(x=0,y=0,w=source['width_mm'],h=source['height_mm'])
        works=[dict(key=digest([VERSION,source['hash'],source['page'],crop]),source_id=source['id'],source_hash=source['hash'],source_page=source['page'],crop=crop,work_width=crop['w'],work_height=crop['h'],slots=[],observations=[],company_bindings={},visual_confirmed=False,analysis_version=VERSION,review_state='AI_PENDING_REVIEW',evidence=dict(method='ACTUAL_TESSERACT_SOURCE_IMAGE_PAGE_HYPOTHESIS',native_illustrator_mapping='UNKNOWN'))]
    for work in works:
        crop=Rect(**work['crop']);kept={slot['id'] for slot in work['slots'] if slot['kind']=='logo'}
        work['slots']=[slot for slot in work['slots'] if slot['id'] in kept];work['observations']=[obs for obs in work['observations'] if obs.get('slot_id') in kept]
        companies=[slot['owner'] for slot in work['slots']];counts=Counter();name=False
        for obs in work['observations']:obs['component_text_predictions']=[]
        for line in text_lines:
            rect=Rect(**line['rect'])
            if not contains(crop,rect):continue
            logo=next((obs for obs in work['observations'] if obs['classification']=='LOGO' and contains(Rect(**obs['region']),rect)),None)
            identity='ocr-'+digest([source['hash'],source['page'],work['key'],line['key']])[:28]
            if logo is not None:logo['component_text_predictions'].append(dict(id=identity,rect=line['rect'],text=line['text']));continue
            semantic=recognize(line['text'],model=model);kind=semantic['slot_kind'];slot_id=None
            if kind:
                owner='c'+str(len(companies)+1) if kind=='company' else 'p1'
                if kind=='company':companies.append(owner)
                if kind=='name':name=True
                slot_id=identity;work['slots'].append(asdict(Slot(kind,owner,Rect(rect.x-crop.x,rect.y-crop.y,rect.w,rect.h),index=counts[kind],id=identity,required=kind=='name')));counts[kind]+=1
            work['observations'].append(dict(id='obs-'+identity,slot_id=slot_id,text=line['text'],region=line['rect'],object_type='TEXT',classification='FIELD' if kind else 'UNKNOWN',semantic=semantic,ocr_word_confidences=line['word_confidences'],prior_prediction='ACTUAL_OCR_UNCONFIRMED'))
        work['company_bindings']={'p1':companies} if name else {}
        work['evidence']['ocr']=dict(executed=True,algorithm_version=VERSION,model_hashes={m['language']:m['sha256'] for m in record['models']},configuration=record['configuration'],all_page_lines=len(text_lines),confidence_filter_applied=False,original_native_text_or_identity_verified=False)
    return works
