from pathlib import Path
import os,subprocess,select,signal,json,time,hashlib
root=Path('/workspace/template-Ai');native=Path('/workspace/template-ai-gui-tools/root');out=Path('/tmp/template-ai-native-input-003');out.mkdir(exist_ok=True)
env=os.environ.copy();env['QT_QPA_PLATFORM']='xcb';env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1'
readfd,writefd=os.pipe();server=None
try:
 with (out/'xvfb.log').open('w') as log:
  server=subprocess.Popen([str(native/'usr/bin/Xvfb'),'-displayfd',str(writefd),'-screen','0','1600x1100x24','-nolisten','tcp'],pass_fds=(writefd,),stdout=log,stderr=log,env=env,start_new_session=True)
 os.close(writefd);writefd=-1
 assert select.select([readfd],[],[],10)[0]
 display=os.read(readfd,64).decode().strip();assert display.isdigit();env['DISPLAY']=':'+display
 started=time.monotonic()
 with (out/'capture.log').open('w') as log:
  result=subprocess.run([str(root/'.venv/bin/python'),'tools/capture_input_integration.py','--folder',str(out)],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file() and p.name!='native-evidence.json'}
 (out/'native-evidence.json').write_text(json.dumps(dict(status='PASS' if result.returncode==0 else 'FAIL',source_commit='73c77229c385c28b6bd568d94149f12f60913cd0',platform='xcb on local Xvfb;TCP disabled',elapsed_seconds=time.monotonic()-started,original_capture_scenarios=5,expected_screenshots=6,new_unique_test_count_increment=0,files=files),indent=2)+'\n')
 print('Native existing-input capture exit',result.returncode,flush=True)
 raise SystemExit(result.returncode)
finally:
 os.close(readfd)
 if writefd>=0:os.close(writefd)
 if server and server.poll() is None:
  os.killpg(server.pid,signal.SIGTERM);server.wait(timeout=3)
