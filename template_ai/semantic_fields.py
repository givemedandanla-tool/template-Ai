"""Offline, explainable field meaning; candidates never become source truth.

Phone numbering metadata comes from libphonenumber via python-phonenumbers.
Other recognizers use bounded Unicode text, explicit labels, content and URLs.
The character model is multinomial Naive Bayes with Laplace smoothing. It only
uses explicitly authorized, confirmed examples and can abstain. Its score is
not a calibrated probability. No paid service or source-file upload is used.
"""
from collections import Counter, defaultdict
import math
import re
import unicodedata
from urllib.parse import urlsplit
import phonenumbers as pn

VERSION = 'semantic-fields-1/phonenumbers-' + pn.__version__
TYPES = {'email','social_id','landline','mobile','phone','fax','address','title','name','company'}
TYPE_LABELS=dict(email='電子郵件',social_id='社群軟體ID',landline='市內電話',mobile='手機',phone='電話（固網／行動類型未能區分）',fax='傳真',address='地址',title='職稱',name='姓名',company='公司',unknown='語意待確認')
SLOTS = dict(email='email',landline='phone',mobile='phone',phone='phone',fax='phone',address='address',title='title',name='name',company='company')
PLATFORMS = {'line':'line','instagram':'ig','ig':'ig','facebook':None,'fb':None,'telegram':None,'whatsapp':None,'wechat':None,'微信':None,'threads':None,'x':None}
LABEL = re.compile(r'^\s*(姓名|name|公司|company|e-?mail|電子郵件|電郵|mail|手機|行動電話|mobile|cell(?:phone)?|tel(?:ephone)?|電話|市話|市內電話|phone|fax|傳真|住址|地址|address|職稱|職位|title|position|line|ig|instagram|facebook|fb|telegram|whatsapp|wechat|微信|threads)\s*[:：]\s*(.+)$',re.I)


def normalized(value):
    if not isinstance(value,str) or not value.strip() or len(value)>2048 or any(ord(c)<32 and c not in '\t\n\r' for c in value):
        raise ValueError('語意輸入需1～2048字且不可含控制字元')
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',value)).strip()


def features(value):
    text=normalized(value).casefold();words=re.findall(r'[a-z]+|[\u3400-\u9fff]',text)
    chars='^'+re.sub(r'\d','#',text)+'$'
    return Counter(['w:'+w for w in words]+['c:'+chars[i:i+n] for n in (2,3) for i in range(len(chars)-n+1)])


class CharacterModel:
    """Explicitly authorized text-only training; no access to source/customer DB."""
    def __init__(self,examples):
        self.counts=defaultdict(Counter);self.documents=Counter();self.vocabulary=set();self.sample_ids=[]
        if len(examples)>2000:raise ValueError('字串模型每版至多2000個明確樣本')
        seen=set();characters=0
        for row in examples:
            if row.get('confirmed') is not True or row.get('use')!='SEMANTIC_CLASSIFICATION_LOCAL':continue
            kind=row.get('semantic_type');identity=row.get('sample_id')
            if kind not in TYPES or not isinstance(identity,str) or not identity or identity in seen:raise ValueError('語意樣本類型／stable ID不合法或重複')
            characters+=len(row['text'])
            if characters>250000:raise ValueError('本次語意訓練文字超過25萬字，請縮小範圍')
            seen.add(identity);tokens=features(row['text']);self.counts[kind].update(tokens);self.documents[kind]+=1;self.vocabulary.update(tokens);self.sample_ids.append(identity)
            if len(self.vocabulary)>50000:raise ValueError('語意詞彙特徵超過5萬，本版需縮小訓練範圍')

    def predict(self,value):
        tokens=features(value);known=sum(n for t,n in tokens.items() if t in self.vocabulary);total=sum(tokens.values())
        if len(self.documents)<2 or total==0 or known/total<.35:return None
        scores=[];n=sum(self.documents.values());v=len(self.vocabulary)
        for kind,counts in self.counts.items():
            denominator=sum(counts.values())+v
            score=math.log(self.documents[kind]/n)+sum(count*math.log((counts[token]+1)/denominator) for token,count in tokens.items() if token in self.vocabulary)
            scores.append((score,kind))
        scores.sort(reverse=True)
        # Requiring multiple documents and a per-token margin avoids a confident
        # looking answer from a lone memorized phrase / nearly tied categories.
        margin=(scores[0][0]-scores[1][0])/max(1,known)
        if self.documents[scores[0][1]]<2 or margin<.12:return None
        return dict(semantic_type=scores[0][1],margin=round(margin,6),score_kind='UNCALIBRATED_LOG_LIKELIHOOD_MARGIN',sample_ids=list(self.sample_ids))


def recognize(value,region='TW',model=None):
    raw=normalized(value);match=LABEL.fullmatch(raw);label=match[1].casefold() if match else '';content=match[2].strip() if match else raw
    candidates=[];signals=[];platform=None;normal=content
    def add(kind,why):
        if kind not in candidates:candidates.append(kind)
        signals.append(why)
    if re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>.]+',content):add('email','完整郵件帳號與網域結構')
    if label in PLATFORMS and re.fullmatch(r'@?[\w.\-+]{1,128}',content):
        platform=label;add('social_id','明確社群平台標籤：'+label)
    parsed=urlsplit(content if re.match(r'https?://',content,re.I) else 'https://'+content)
    host=(parsed.hostname or '').casefold();hosts={'line.me':'line','instagram.com':'instagram','www.instagram.com':'instagram','facebook.com':'facebook','www.facebook.com':'facebook','t.me':'telegram','wa.me':'whatsapp','threads.net':'threads','x.com':'x'}
    if host in hosts and parsed.path.strip('/') and not candidates:
        platform=hosts[host];add('social_id','明確社群平台URL：'+host)
    # An ID without a platform and an arbitrary digit sequence remain unknown.
    phone_label=label in ('手機','行動電話','mobile','cell','cellphone','tel','telephone','電話','市話','市內電話','phone','fax','傳真')
    phone_text=re.sub(r'(?:分機|轉|ext\.?|extension)\s*[:：]?\s*(\d{1,8})$',r' ext. \1',content,flags=re.I)
    if not candidates and re.fullmatch(r'[+()\d .\-]+(?:\s*ext\. \d{1,8})?',phone_text,re.I):
        try:
            number=pn.parse(phone_text,region)
            if pn.is_valid_number(number):
                typed=pn.number_type(number)
                kind={pn.PhoneNumberType.MOBILE:'mobile',pn.PhoneNumberType.FIXED_LINE:'landline'}.get(typed,'phone')
                if label in ('fax','傳真'):kind='fax'
                add(kind,'libphonenumber有效號碼／類型：'+str(typed)+'；預設地區：'+region)
                normal=pn.format_number(number,pn.PhoneNumberFormat.E164)+((' ext. '+number.extension) if number.extension else '')
                if label in ('手機','行動電話','mobile','cell','cellphone') and kind=='landline':signals.append('標籤手機與固網號碼矛盾；需核對')
                if label in ('市話','市內電話') and kind=='mobile':signals.append('標籤市話與行動號碼矛盾；需核對')
            elif phone_label:signals.append('電話標籤存在但號碼未通過地區規則')
        except pn.NumberParseException:signals.append('電話無法解析')
    if not candidates and (label in ('地址','住址','address') or re.search(r'(?:[\u3400-\u9fff]{2,}[縣市].*(?:路|街|巷|大道).*\d+(?:號|樓))|(?:\b\d+\s+[\w .-]+\s+(?:street|st\.?|road|rd\.?|avenue|ave\.?|boulevard|blvd\.?)\b)',content,re.I)):
        if re.search(r'\d',content) and len(content)>=6:add('address','地址標籤或行政區／道路／門牌語意；未做郵政有效性核驗')
    title_terms=r'(?:董事長|副總經理|總經理|經理|副理|協理|主任|總監|工程師|設計師|顧問|專員|教授|醫師|律師|執行長|研究員|業務代表|chief\s+\w+(?:\s+officer)?|(?:senior\s+|software\s+|sales\s+)?(?:engineer|manager|director|designer|consultant|developer)|CEO|CTO|CFO|president|founder)'
    if not candidates and (label in ('職稱','職位','title','position') or re.fullmatch(title_terms,content,re.I)):
        if not re.fullmatch(r'[\d\W]+',content):add('title','明確職稱標籤或中英文職務詞彙')
    if not candidates and re.search(r'(?:股份有限公司|有限公司|\b(?:Inc\.?|Ltd\.?|LLC|Corporation))$',content,re.I):add('company','法人結尾詞；公司身分仍須來源核對')
    if not candidates and label in ('姓名','name','公司','company') and not re.fullmatch(r'[\d\W]+',content):
        add('name' if label in ('姓名','name') else 'company','明確姓名／公司標籤；身分仍須來源核對')
    learned=None
    if not candidates and model is not None and not content.startswith('@'):
        learned=model.predict(content)
        if learned:add(learned['semantic_type'],'確認且授權的字元Naive Bayes；非校準分數')
    kind=candidates[0] if len(candidates)==1 else 'unknown'
    slot_kind=PLATFORMS.get(platform) if kind=='social_id' else SLOTS.get(kind)
    if kind=='unknown':signals.append('證據不足；保留未知，不從位置推定人物或職稱')
    if kind=='social_id' and slot_kind is None:signals.append('已辨識平台；現有輸出欄位尚未支援此平台，需人工映射')
    return dict(version=VERSION,raw=value,normalized=normal,semantic_type=kind,slot_kind=slot_kind,platform=platform,
                candidates=candidates,signals=signals,model=learned,state='PENDING_REVIEW',confidence='UNCALIBRATED_CANDIDATE',region=region)


def review_issues(work,facts,confirmation_valid=False):
    """Current unresolved text evidence for the shared work exception center."""
    import hashlib,json
    confirmed=set((facts.get('confirmation') or {}).get('observation_ids',[])) if confirmation_valid else set();result=[]
    for observation in facts['observations']:
        if observation['object_type']!='TEXT' or observation['id'] in confirmed:continue
        row=recognize(observation['text']);reasons=[]
        if row['semantic_type']=='unknown':reasons.append('字串語意證據不足，需核對類型／歸屬或註記排除')
        if row['semantic_type']=='social_id' and row['slot_kind'] is None:reasons.append('已辨識社群平台，但現有輸出欄位尚未支援，需明確映射')
        reasons.extend(s for s in row['signals'] if '矛盾' in s)
        if not reasons:continue
        reason='；'.join(reasons);slot_ids=[observation['slot_id']] if observation.get('slot_id') else []
        identity=hashlib.sha256(json.dumps([work['id'],observation['id'],reason],ensure_ascii=False).encode()).hexdigest()
        result.append(dict(id=identity,code='SEMANTIC_REVIEW',severity='REVIEW',reason=reason,slot_ids=slot_ids,observation_id=observation['id'],
            work_id=work['id'],work_revision=work['revision'],work_name=work['name'],source_id=work['source_id'],locatable=True))
    return result
