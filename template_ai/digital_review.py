"""Explicit current-format snapshot review in the original transient output session."""
import copy,re,time
from .training_store import digest,text
from .model import new_id
from .background import file_digest
from .digital_preflight import inspect_candidate,validate_scope
from .digital_output_proof import decoded_image,pdf_evidence


def pdf_signature(value):
    vector=('m','l','c','re','h','S','s','f','f*','B','B*','b','b*')
    fonts=sorted((re.sub(r'^/[A-Z]{6}\+','/',f['base_font']),f['subtype'],f['embedded']) for f in value['fonts'])
    images=sorted((i['width'],i['height'],i.get('filter'),i.get('stream_digest')) for i in value['image_xobjects'])
    return dict(size_mm=[round(v,6) for v in value['size_mm']],fonts=fonts,images=images,vector={k:value['operator_histogram'].get(k,0) for k in vector},text_operators=value['text_operator_count'])


def confirm(candidate,proof,actor,evidence,approved=False):
    if approved is not True:raise ValueError('需明確核對目前格式／尺寸實際快照，不能自動核准')
    text(actor,'格式核對者',120);text(evidence,'實際快照核對依據',2000)
    validate_scope(candidate,proof['scope']);value=inspect_candidate(candidate,proof['scope']['format'],proof['scope']['dpi'])
    if not value['can_encode']:raise ValueError('目前來源／字型／幾何／像素條件仍阻擋，核對快照不能略過硬性Gate')
    file=proof.get('exact_file')
    if not file or file_digest(file['path'])!=file['sha256']:raise ValueError('需本格式真正編碼、成品尺寸且未變更的原尺寸PREVIEW快照')
    decoded_image(file['path'],proof['scope']['size_mm'],proof['scope']['dpi']);pdf=pdf_evidence(file['path']) if proof['scope']['format']=='PDF' else None
    if pdf and not pdf['all_fonts_embedded']:raise ValueError('實際PDF字型未內嵌，不可略過')
    validate_scope(candidate,proof['scope']);result=dict(id=new_id(),mode='EXACT_DIGITAL_FORMAT_REVIEW',scope=copy.deepcopy(proof['scope']),file=copy.deepcopy(file),pdf_signature=pdf_signature(pdf) if pdf else None,actor=actor,evidence=evidence,at=time.time(),reviewed=True,physical_print_verified=False,scope_allows_other_versions=False)
    result['digest']=digest(result);return result


def validate(candidate,pin,receipt):
    if not isinstance(receipt,dict) or receipt.get('mode')!='EXACT_DIGITAL_FORMAT_REVIEW' or receipt.get('reviewed') is not True or receipt.get('digest')!=digest({k:v for k,v in receipt.items() if k!='digest'}):raise ValueError('此PDF／JPG需目前格式、尺寸與DPI的實際快照核對；請由既有印前檢查完成')
    if receipt['scope']!=pin:raise ValueError('格式／尺寸／輸入／Logo／來源已改變，舊快照核對不能沿用')
    validate_scope(candidate,pin)
    if file_digest(receipt['file']['path'])!=receipt['file']['sha256']:raise ValueError('已核對實際快照失聯／改變，不能發布正式輸出')
    return receipt
