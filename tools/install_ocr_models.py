"""下載官方固定 Git 版本的 OCR 語言資料，驗證 Git blob 與 SHA256。

模型只放本機 ignored local-data，不寫入 Git；不呼叫 OCR 雲端服務。
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

COMMIT='65727574dfcd264acbb0c3e07860e4e9e9b22185'
FILES={'chi_tra.traineddata':'1955cd8b8d076b898616e9c2c1ace65b43105356',
       'eng.traineddata':'bbef4675053b5b468cdb477053e28b1c698ba08e',
       'LICENSE':'d645695673349e3947e8e5ae42332d0ac3164cd7'}


def install(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);records=[]
    for name,expected in FILES.items():
        target=directory/name
        url=f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{COMMIT}/{name}'
        if target.exists():data=target.read_bytes()
        else:
            with urllib.request.urlopen(url,timeout=45) as response:data=response.read(20_000_001)
        if len(data)>20_000_000:raise ValueError('模型超過下載預算')
        actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if actual!=expected:raise ValueError(f'{name}與固定官方Git blob不符；未覆寫或使用不可信模型')
        if not target.exists():
            with target.open('xb') as stream:stream.write(data)
        records.append(dict(name=name,bytes=len(data),git_blob_sha1=actual,
                            sha256=hashlib.sha256(data).hexdigest(),source=url))
    manifest=dict(repository='tesseract-ocr/tessdata_fast',tag='4.1.0',commit=COMMIT,
                  integrity='Git blob IDs obtained from the official fetched tag tree',files=records)
    (directory/'MODEL_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parents[1]/'local-data/tessdata')
    args=parser.parse_args();result=install(args.directory)
    print(json.dumps(dict(commit=result['commit'],verified_files=len(result['files']))))
