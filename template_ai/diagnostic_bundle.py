"""Offline, bounded, closed-schema reports; never extracts a ZIP or executes supplied HTML."""
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile
from . import __version__
from .diagnostic_schema import MESSAGES, NUMBER_KEYS, KINDS, SEVERITIES

MAX_BYTES = 2 * 1024 * 1024
MAX_ISSUES = 2000
NAMES = {'report.html', 'report.json', 'manifest.json'}
STAGES = {'DATA_PROCESSING', 'TEMPLATE_GENERATION', 'INPUT_OUTPUT'}
STATES = {'NOT_CHECKED', 'LOCAL_SCOPE_CHECKED', 'PENDING_LAYOUT', 'BLOCKED', 'DIGITAL_VALID',
          'STALE_RESULT', 'PARTIAL', 'RUNNING', 'COMPLETED', 'CANCELLED', 'FAILED', 'FAILED_SYSTEM'}
SOURCE_STATES = {'NOT_CHECKED', 'OK', 'MISSING', 'CHANGED', 'UNREADABLE'}


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def exact(data, keys):
    if type(data) is not dict or set(data) != set(keys):
        raise ValueError('報告格式含未允許或缺少欄位')


def number(value, *, nullable=False, maximum=1e9):
    if value is None and nullable:
        return
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > maximum:
        raise ValueError('報告數值不合法')


def validate(data):
    exact(data, {'schema_version','report_id','created_utc','app_version','historical','nonformal',
                 'stage','stages','status','source_health','model_quality','physical_print',
                 'scope','progress','issues','measurements','omitted_issues','privacy','object_revision','classification'})
    if data['schema_version'] != 1 or type(data['schema_version']) is not int:
        raise ValueError('不支援此報告版本')
    if not isinstance(data['report_id'], str) or not re.fullmatch('[0-9a-f]{32}',data['report_id']):
        raise ValueError('報告識別不合法')
    if not isinstance(data['created_utc'],str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',data['created_utc']):
        raise ValueError('報告時間不合法')
    if not isinstance(data['app_version'],str) or not re.fullmatch(r'\d{1,3}\.\d{1,3}\.\d{1,3}',data['app_version']):
        raise ValueError('報告程式版本不合法')
    if data['historical'] is not True or data['nonformal'] is not True or data['privacy'] != 'SAFE_ALLOWLIST_NO_SOURCE_ATTACHMENTS':
        raise ValueError('缺少歷史／非正式／安全內容標記')
    if data['stage'] not in STAGES or data['status'] not in STATES or data['source_health'] not in SOURCE_STATES:
        raise ValueError('報告狀態不合法')
    exact(data['stages'],STAGES)
    if any(v not in STATES for v in data['stages'].values()):raise ValueError('環節狀態不合法')
    if any(v != 'NOT_VERIFIED' for v in (data['model_quality'],data['physical_print'])):
        raise ValueError('報告不得自行宣稱模型或印刷驗證')
    number(data['object_revision'],nullable=True)
    if data['classification'] is not None:
        c=data['classification']
        exact(c,{'gold_count','predicted_count','critical_owner_errors','gate','prediction_origin','metrics','versions'})
        if c['gate'] not in ('FAILED_CRITICAL','EVIDENCE_INSUFFICIENT') or c['prediction_origin']!='USER_SUPPLIED_RECORDS_NOT_EXECUTED_MODEL_INFERENCE' or c['versions']!='USER_SUPPLIED_LABELS_NOT_VERIFIED_LOCAL_ONLY':raise ValueError('分類紀錄不能冒稱模型品質驗證')
        for k in ('gold_count','predicted_count','critical_owner_errors'):number(c[k])
        exact(c['metrics'],KINDS-{'unknown'})
        for m in c['metrics'].values():
            exact(m,{'tp','fp','fn','precision','recall'})
            for k,v in m.items():number(v,nullable=k in ('precision','recall'))
    exact(data['scope'],{'sources','works','candidates','fields','width_mm','height_mm'})
    for k,v in data['scope'].items():
        number(v,nullable=True)
        if v is not None and v<0:raise ValueError('範圍分母不合法')
    exact(data['progress'],{'state','total','checked','calculated','failed','unstarted','global_unsolvable'})
    if data['progress']['state'] not in STATES or data['progress']['global_unsolvable'] is not False:
        raise ValueError('報告不能自行聲稱全域無解')
    for k in ('total','checked','calculated','failed','unstarted'):
        v=data['progress'][k]
        if v is not None and (type(v) is not int or not 0<=v<=1_000_000):raise ValueError('工作分母不合法')
    p=data['progress']
    if all(p[k] is not None for k in ('total','checked','unstarted')) and p['checked']+p['unstarted']!=p['total']:
        raise ValueError('工作分母不一致')
    for group in ('issues','measurements'):
        if type(data[group]) is not list or len(data[group])>MAX_ISSUES:raise ValueError('報告超出問題預算')
        for row in data[group]:
            exact(row,{'code','severity','target','fields','kind','parameters','locatable','action','origin_stage','impact_stage'})
            if row['origin_stage'] not in STAGES or row['impact_stage'] not in STAGES:raise ValueError('問題發生與影響環節不合法')
            if row['code'] not in MESSAGES or row['severity'] not in SEVERITIES or row['kind'] not in KINDS:
                raise ValueError('未知報告問題類型')
            if not isinstance(row['target'],str) or not re.fullmatch(r'(?:人物|公司|作品|候選|模板|來源|範圍)[1-9][0-9]{0,5}',row['target']):
                raise ValueError('只允許報告內匿名代號')
            if type(row['fields']) is not list or len(row['fields'])>200 or any(not isinstance(s,str) or not re.fullmatch(r'欄位[1-9][0-9]{0,5}',s) for s in row['fields']):
                raise ValueError('欄位匿名代號不合法')
            if type(row['locatable']) is not bool or row['action']!='LOCAL_REVIEW_THEN_REVALIDATE':raise ValueError('不允許報告執行指令')
            if type(row['parameters']) is not dict or not set(row['parameters'])<=NUMBER_KEYS:raise ValueError('未核准報告參數')
            for v in row['parameters'].values():number(v,nullable=True)
    if type(data['omitted_issues']) is not int or data['omitted_issues']<0:raise ValueError('省略數不合法')
    if len(encoded(data))>MAX_BYTES:raise ValueError('報告超過大小預算')
    return data


def report_html(data):
    validate(data)
    titles={'DATA_PROCESSING':'資料處理','TEMPLATE_GENERATION':'模板生成','INPUT_OUTPUT':'輸入／產出作品'}
    rows=''.join('<tr><td>'+html.escape(str(i+1))+'</td><td>'+html.escape(r['target']+' '+','.join(r['fields']))+
                 '</td><td>'+html.escape(r['severity']+'／'+r['code'])+'</td><td>'+html.escape(MESSAGES[r['code']])+
                 '</td><td>回到原問題核對後重新驗證</td></tr>' for i,r in enumerate(data['issues']))
    return ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; base-uri \'none\'; form-action \'none\'">'
            '<title>診斷報告</title></head><body><h1>診斷報告 · 歷史快照 · 非正式</h1>'
            '<p>環節：'+titles[data['stage']]+'；狀態：'+data['status']+'；時間：'+data['created_utc']+'</p>'
            '<p>只代表列明的檢查範圍；不是當前驗證、模型品質、視覺一致或正式印刷可用證明。'
            '安全交接版省略原始文字、路徑與原稿。匿名代號僅限此報告；校驗碼不保證作者或內容真實。</p>'
            '<table border="1"><tr><th>序號</th><th>對象</th><th>類型</th><th>原因</th><th>處理</th></tr>'+rows+'</table>'
            '<h2>完整檢查範圍、數值、版本與未驗證項</h2><pre>'+html.escape(encoded(data).decode())+'</pre></body></html>').encode()


def build_bundle(data):
    public=encoded(validate(data)); page=report_html(data)
    manifest=encoded({'schema_version':1,'integrity':'SHA256_NOT_SIGNATURE',
                      'files':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in [('report.json',public),('report.html',page)]}})
    if sum(map(len,(public,page,manifest)))>MAX_BYTES:raise ValueError('報告超過2MiB，請縮小範圍')
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
        for name,body in [('report.json',public),('report.html',page),('manifest.json',manifest)]:
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_STORED;info.create_system=3;info.external_attr=0o600<<16
            z.writestr(info,body)
    return out.getvalue()


def parse_json(body):
    def pairs(rows):
        result={}
        for k,v in rows:
            if k in result:raise ValueError('JSON有重複欄位')
            result[k]=v
        return result
    return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda v: (_ for _ in ()).throw(ValueError('不允許非有限數值')))


def read_bundle(raw):
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES+65536:raise ValueError('報告檔案超出預算')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            entries=z.infolist()
            if z.comment or any(i.comment or i.extra for i in entries):raise ValueError('不允許報告隱藏中介資料')
            if len(entries)!=3 or {i.filename for i in entries}!=NAMES:raise ValueError('只允許三個固定報告條目')
            if sum(i.file_size for i in entries)>MAX_BYTES:raise ValueError('解壓內容超出預算')
            for i in entries:
                mode=i.external_attr>>16
                if stat.S_ISLNK(mode) or i.flag_bits&1 or i.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) or i.file_size>max(1,i.compress_size)*200:
                    raise ValueError('不允許此壓縮／連結／加密條目')
            bodies={i.filename:z.read(i) for i in entries}
        m=parse_json(bodies['manifest.json']);exact(m,{'schema_version','integrity','files'})
        if m['schema_version']!=1 or m['integrity']!='SHA256_NOT_SIGNATURE':raise ValueError('校驗格式不合法')
        exact(m['files'],{'report.html','report.json'})
        for n in m['files']:
            exact(m['files'][n],{'bytes','sha256'})
            if m['files'][n]!={'bytes':len(bodies[n]),'sha256':sha(bodies[n])}:raise ValueError('報告損壞或不一致')
        data=validate(parse_json(bodies['report.json']))
        if bodies['report.html']!=report_html(data):raise ValueError('HTML與JSON不是同份安全內容')
        if raw!=build_bundle(data):raise ValueError('報告含非標準封裝或額外資料')
        return data
    except (zipfile.BadZipFile,UnicodeError,KeyError,TypeError,RecursionError,RuntimeError) as error:
        raise ValueError('無法驗證報告格式') from error


def save_bundle(target,raw,check=lambda:None):
    """Same-directory staging + exclusive hard-link publication, matching the artwork writer policy."""
    read_bundle(raw)
    target=Path(target)
    if target.suffix.lower()!='.zip' or not target.parent.is_dir():raise ValueError('請選既有本機資料夾及ZIP檔名')
    if target.exists() or target.is_symlink():raise FileExistsError('不覆寫既有報告，請更名')
    check()
    fd,name=tempfile.mkstemp(prefix='.diagnostic-',suffix='.zip',dir=target.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        read_bundle(Path(name).read_bytes());check()
        from .safe_publish import publish_complete
        publish_complete(name,target,check)
    finally:
        Path(name).unlink(missing_ok=True)
    return target
