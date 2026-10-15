"""Authenticated local database snapshots; external asset paths are not portable assets."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import zipfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC=b'TABI1';LIMIT=64*1024*1024

def key(password,salt):
    if len(password)<12 or len(password)>1024:raise ValueError('密碼需12至1024字；遺失無法還原，勿與備份同存')
    return Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(password.encode())

def backup(library,target,password):
    target=Path(target)
    if target.exists():raise FileExistsError('不覆寫既有檔案')
    if library.db.in_transaction:raise ValueError('資料庫仍在交易中，稍後重試')
    with tempfile.TemporaryDirectory(dir=library.root) as tmp:
        path=Path(tmp)/'library.sqlite3'
        with sqlite3.connect(path) as other:
            library.db.backup(other)
            if other.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or other.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('快照完整性失敗')
        if path.stat().st_size>LIMIT:raise ValueError('本版快照上限64 MiB')
        data=path.read_bytes();manifest={'schema':1,'scope':'DATABASE_ONLY_PARTIAL','database_sha256':hashlib.sha256(data).hexdigest(),'database_bytes':len(data),'assets_included':False,'restoration':'EXTERNAL_ASSETS_REQUIRE_RELINK_AND_REVALIDATION','source_ids':[s['id'] for s in library.list_sources()],'logo_ids':[a['id'] for a in library.logos()],'font_hashes':[a.get('hash') for a in library.fonts()]}
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as z:z.writestr('library.sqlite3',data);z.writestr('manifest.json',json.dumps(manifest))
        salt=os.urandom(16);nonce=os.urandom(12);blob=MAGIC+salt+nonce+AESGCM(key(password,salt)).encrypt(nonce,stream.getvalue(),MAGIC)
        # authenticate own output before publishing a file, never log key/password.
        if AESGCM(key(password,salt)).decrypt(nonce,blob[33:],MAGIC)!=stream.getvalue():raise ValueError('加密驗證失敗')
        try:
            with target.open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
        except BaseException:
            # An exclusive-create failure must never delete someone else's file.
            raise
    return {**manifest,'encrypted':True,'authenticated':True,'test_restore':False}

def restore(archive,target,password):
    archive=Path(archive);target=Path(target)
    if target.exists():raise FileExistsError('僅可還原到不存在的新目錄，不覆寫目前資料')
    if archive.stat().st_size>LIMIT+1024*1024:raise ValueError('備份超過本版上限')
    blob=archive.read_bytes()
    if not blob.startswith(MAGIC) or len(blob)<49:raise ValueError('不是支援的加密備份')
    try:plain=AESGCM(key(password,blob[5:21])).decrypt(blob[21:33],blob[33:],MAGIC)
    except Exception as e:raise ValueError('密碼錯誤或備份損壞；未修改現有資料') from e
    with zipfile.ZipFile(io.BytesIO(plain)) as z:
        if sorted(z.namelist())!=['library.sqlite3','manifest.json'] or any(i.file_size>LIMIT for i in z.infolist()):raise ValueError('備份封裝不合法')
        manifest=json.loads(z.read('manifest.json'));data=z.read('library.sqlite3')
    if manifest.get('schema')!=1 or manifest.get('database_bytes')!=len(data) or manifest.get('database_sha256')!=hashlib.sha256(data).hexdigest():raise ValueError('備份Manifest不符')
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        probe=Path(tmp)/'db.sqlite3';probe.write_bytes(data)
        with sqlite3.connect('file:'+str(probe)+'?mode=ro',uri=True) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('隔離資料庫檢查失敗')
            if not {'templates','sources','logos'}<={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}:raise ValueError('不支援的schema')
        os.mkdir(target,0o700)
        try:
            with (target/'library.sqlite3').open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            (target/'RESTORE_PARTIAL.json').write_text(json.dumps(manifest,indent=2))
        except BaseException:shutil.rmtree(target);raise
    return {**manifest,'database_integrity':'PASS','external_assets':'NOT_RESTORED','production_ready':False}
