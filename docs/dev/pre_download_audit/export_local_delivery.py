"""Create base-relative local recovery delivery; never push or assert remote provenance."""
from pathlib import Path
import argparse,hashlib,io,json,os,subprocess,sys,tarfile,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[3]
BASE='0e7b8aee82331ff6efa02a1a8233ff85689b660a'
def git(*args,cwd=ROOT,**kw):return subprocess.run(['git',*args],cwd=cwd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kw)
def sha(data):return hashlib.sha256(data).hexdigest()
def tree(rev):
 result={}
 for line in git('ls-tree','-r','-z',rev).stdout.split(b'\0'):
  if not line:continue
  info,path=line.split(b'\t',1);mode,kind,blob=info.decode().split();result[path.decode()]=dict(mode=mode,kind=kind,blob=blob)
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.relative_to(ROOT/'.cache');assert not git('status','--porcelain').stdout,'Commit tracked delivery first'
 audit=ROOT/'docs/dev/pre_download_audit';full=json.loads((audit/'full-regression-final-009/summary.json').read_text());assert full['software_execution']=='PASS' and full['planned']==1920 and full['original_test_ids_preserved'] and full['source_unchanged_during_run']
 stock=json.loads((audit/'gui-stock-captures-final-002/summary.json').read_text());assert stock['status']=='PASS' and stock['passed']==27 and stock['source_unchanged']
 native=json.loads((audit/'native-gui-final-005/native-runner-result.json').read_text());assert native['status']=='PASS' and native['source_unchanged']
 sys.path.insert(0,str(ROOT/'tools'))
 from dev_common import manifest as source_manifest
 qualified=json.loads((audit/'full-regression-final-009/source.json').read_text());assert source_manifest(code_only=True)==qualified['source_manifest'],'Source no longer equals final tested code'
 head=git('rev-parse','HEAD').stdout.decode().strip();branch=git('branch','--show-current').stdout.decode().strip();out.mkdir(parents=True,exist_ok=False)
 before=tree(BASE);after=tree(head);names=[x.decode() for x in git('diff','--no-renames','--name-only','-z',BASE,head).stdout.split(b'\0') if x];assert names
 for name in names:
  path=Path(name);assert not path.is_absolute() and '..' not in path.parts and '.cache' not in path.parts and '.git' not in path.parts
  assert path.suffix.casefold() not in ('.sqlite','.sqlite3','.db','.ttf','.otf','.woff','.woff2'),name
 patch=out/'changes.patch'
 with patch.open('wb') as stream:subprocess.run(['git','diff','--binary','--no-renames',BASE,head],cwd=ROOT,stdout=stream,check=True)
 bundle=out/'history.bundle';git('bundle','create',str(bundle),BASE+'..HEAD');verification=git('bundle','verify',str(bundle));heads=git('bundle','list-heads',str(bundle)).stdout.decode();assert head in heads
 records={}
 for name in names:
  info=after.get(name)
  if info is None:records[name]=dict(state='DELETED');continue
  assert info['kind']=='blob',name
  local=ROOT/name;data=os.readlink(local).encode() if info['mode']=='120000' else local.read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();assert blob==info['blob'],name
  records[name]=dict(state='PRESENT',mode=info['mode'],git_blob_sha1=blob,sha256=sha(data),bytes=len(data))
 # Restore only changed baseline paths, avoiding unrelated historical attachments.
 with tempfile.TemporaryDirectory(prefix='template-ai-audit-restore-',dir='/tmp') as temp:
  restored=Path(temp);git('init','-q',cwd=restored)
  old_names=[n for n in names if n in before]
  for start in range(0,len(old_names),100):
   data=git('archive','--format=tar',BASE,'--',*old_names[start:start+100]).stdout
   with tarfile.open(fileobj=io.BytesIO(data)) as archive:archive.extractall(restored,filter='data')
  git('apply','--binary',str(patch),cwd=restored)
  for name,info in records.items():
   path=restored/name
   if info['state']=='DELETED':assert not path.exists() and not path.is_symlink(),name
   else:
    data=os.readlink(path).encode() if info['mode']=='120000' else path.read_bytes();assert sha(data)==info['sha256'],name
    if info['mode']!='120000':assert bool(path.stat().st_mode & 0o111)==(info['mode']=='100755'),name
  restore=dict(status='PASS',changed_paths=len(records),all_content_hashes_match=True,baseline='Only exact changed BASE paths materialized; git apply --binary actual restoration',bundle_prerequisites_verified_in_existing_repository=True,not_claimed='Standalone full clone; BASE commit must already exist for bundle fetch. Remote provenance not claimed.')
 manifest=dict(schema=1,qualification='LOCAL_ONLY_NOT_REMOTE_VERIFIED',base=BASE,head=head,branch=branch,changed_files=records,restore=restore,private_data_included=False,exe_included=False,source_test_commit=qualified['commit'],verification=dict(full_regression=full,stock_captures=stock,native_status=native['status']),no_remote_write=True)
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 guide='''這是本機開發還原包，不是 EXE。沒有推送 GitHub，不是 REMOTE_VERIFIED。\n\n先保留原本未提交工作。需要既有 template-Ai 倉庫及 manifest.json 的 base 提交。\n在乾淨、隔離的 checkout 可用 changes.patch 還原全部差異；或在含 base 的 Git 倉庫讀入 history.bundle 並 checkout manifest 的精確 head。overlay/ 是相同提交的變更檔案備份，不含未變更的原有檔案。不要直接覆蓋仍有未保存工作的資料夾。\n\n重新接手：核對 manifest 的 base/head；閱讀 AGENTS.md、STATE 與 ACTIVE_DEVELOPMENT_HANDOFF；執行 python tools/resume_status.py。工具依 debug_tooling/README.md 固定版本重建；私人作品、字型、資料庫及模型自行保存在本機。\n\n本包已在獨立暫存資料夾實際套用 binary patch，逐一核對全部變更檔案 hash。原172需求、AI8包真實資格及 Windows/印刷限制保持不變。完整報告在 docs/dev/pre_download_audit/FINAL_REPORT.md。\n'''
 (out/'READ_ME_繁體中文.txt').write_text(guide)
 target=out/'template-Ai-audit-local-recovery.zip'
 with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
  for path in [patch,bundle,out/'manifest.json',out/'READ_ME_繁體中文.txt']:archive.write(path,path.name)
  for name,info in records.items():
   if info['state']=='PRESENT':
    path=ROOT/name;data=os.readlink(path).encode() if info['mode']=='120000' else path.read_bytes();archive.writestr('overlay/'+name,data)
 receipt=dict(status='LOCAL_SAVED_AND_RESTORE_VERIFIED',head=head,base=BASE,zip=target.name,bytes=target.stat().st_size,sha256=sha(target.read_bytes()),manifest_sha256=sha((out/'manifest.json').read_bytes()),restore=restore,remote='NOT_PUSHED_COST_UNKNOWN',budget='No new paid feature/trial/agent/API/runner; account bill not inspected')
 (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
