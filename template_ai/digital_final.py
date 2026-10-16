"""Hard digital format guards inside the original exclusive publication path.

Codec/readback/source checks do not certify subjective or physical print quality.
"""
from .digital_preflight import inspect_candidate,validate_scope
from .digital_output_proof import decoded_image,pdf_evidence,compare_images,rgb_bytes


def before(candidate,format,dpi,review=None):
    value=inspect_candidate(candidate,format,dpi)
    if not value['can_encode']:
        failed=[r['reason'] for r in value['rows'] if r['status']!='PASS' and r['code'] not in ('ENCODED_FORMAT','PDF_FONT_EMBEDDING')]
        raise ValueError('正式數位輸出預檢阻擋：'+'；'.join(failed))
    if value['scope']['format']!='PNG':
        from .digital_review import validate
        validate(candidate,value['scope'],review)
    return value['scope']


def after(candidate,pin,path,review=None):
    from .render import render_image
    validate_scope(candidate,pin)
    actual=decoded_image(path,pin['size_mm'],pin['dpi']);reference=render_image(candidate,pin['dpi'],False)
    metadata=pdf_evidence(path) if pin['format']=='PDF' else None
    if metadata and not metadata['all_fonts_embedded']:raise ValueError('實際正式PDF含未內嵌字型，未發布檔案')
    if pin['format']!='PNG':
        from .digital_review import validate,pdf_signature
        receipt=validate(candidate,pin,review);reviewed=decoded_image(receipt['file']['path'],pin['size_mm'],pin['dpi'])
        if rgb_bytes(reviewed)!=rgb_bytes(actual):raise ValueError('正式檔實際像素與已核對同格式快照不一致，未發布檔案')
        if metadata and pdf_signature(metadata)!=receipt['pdf_signature']:raise ValueError('正式PDF向量／影像／字型結構與已核對快照不一致，未發布檔案')
    # Lossless PNG has an objective full-resolution byte comparison even when
    # detailed MSE reporting exceeds its separate diagnostic pixel budget.
    exact=rgb_bytes(reference)==rgb_bytes(actual)
    if pin['format']=='PNG' and not exact:raise ValueError('實際PNG卡片像素與目前來源渲染不一致，未發布檔案')
    if metadata:
        from .digital_preflight import logo_sampling
        sources=[logo_sampling(p,pin['dpi']) for p in candidate.items if p.logo]
        if sources and all(r['measurements'].get('source_type')=='VECTOR' for r in sources) and candidate.template.background is None and metadata['image_xobjects']:raise ValueError('純向量Logo的PDF出現無預期點陣替代，未發布檔案')
    validate_scope(candidate,pin)
    return dict(format=pin['format'],size_mm=pin['size_mm'],dpi=pin['dpi'],exact_rgb_match=exact,metrics=compare_images(reference,actual),pdf=metadata,hard_digital_checks_verified=True,physical_print_verified=False,perceptual_fidelity_approved=False)
