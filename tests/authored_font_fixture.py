"""Explicit real-source font records for authored positive integration fixtures.

No product bypass: production checks still require actual asset bytes/use rights.
No font file is copied into the repository's public evidence.
"""
import copy,shutil,subprocess
from pathlib import Path
from template_ai.font_evidence import inspect_font

def bind_authored_fonts(template,manager):
    cache=getattr(manager,'_authored_fixture_fonts',None)
    if cache is None:cache={};manager._authored_fixture_fonts=cache
    for slot in template.slots:
        if slot.kind=='logo' or slot.font_asset is not None:continue
        key=(slot.font,slot.font_style)
        if key not in cache:
            sources=[]
            if shutil.which('fc-match'):
                result=subprocess.run(['fc-match','-f','%{file}\n','--',slot.font],capture_output=True,text=True,timeout=10)
                if result.returncode==0:sources.extend(Path(v) for v in result.stdout.splitlines()[:1])
            sources.extend(Path(v) for v in ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',r'C:\Windows\Fonts\msjh.ttc',r'C:\Windows\Fonts\arial.ttf'))
            found=None
            for path in dict.fromkeys(sources):
                if not path.is_file():continue
                proof=inspect_font(path);faces=[f for f in proof['faces'] if f['family']==slot.font and (not slot.font_style or f['style']==slot.font_style)]
                if faces:found=(path,faces[0]);break
            if found is None:raise AssertionError('Authored fixture requires exact available font source/face: '+repr(key))
            path,face=found
            cache[key]=manager.import_font(path,approved=True,face_index=face['index'],usage_rights=dict(actor='SYNTHETIC_SOURCE_AUTHOR',basis='Explicit source/face and intended authored integration-output use record; no real user/customer licence qualification claimed',print_export=True,pdf_embedding=True))
        asset=cache[key];slot.font_asset=copy.deepcopy(asset);slot.font=asset['families'][0]
    return template
