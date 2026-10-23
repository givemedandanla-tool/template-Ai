import ast,json,os,subprocess,sys,time
from pathlib import Path
root=Path('/workspace/template-Ai');source=ast.parse((root/'tools/run_evidence.py').read_text());commands=[]
for node in ast.walk(source):
 if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute) or node.func.attr!='run' or not node.args or not isinstance(node.args[0],ast.List):continue
 literals=[part.value for part in ast.walk(node.args[0]) if isinstance(part,ast.Constant) and isinstance(part.value,str)]
 script=next((part for part in literals if part.startswith('tools/capture_') and part.endswith('.py')),None)
 option=next((part for part in literals if part in ('--folder','--artifacts-dir')),None)
 if script and option:
  timeout=next((kw.value.value for kw in node.keywords if kw.arg=='timeout' and isinstance(kw.value,ast.Constant)),180)
  commands.append((node.lineno,script,option,timeout))
commands.sort();start=next(i for i,c in enumerate(commands) if c[1]=='tools/capture_workbench_navigation.py')+1
folder=Path('/tmp/input-post-navigation-preflight');folder.mkdir(exist_ok=True)
results=[];environment=os.environ.copy();environment.update(QT_QPA_PLATFORM='offscreen',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
for _,script,option,timeout in commands[start:]:
 begun=time.monotonic();target=folder/(Path(script).stem+'.log')
 with target.open('w') as log:
  try:run=subprocess.run([str(root/'.venv/bin/python'),script,option,str(folder)],cwd=root,env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=timeout*2);code=run.returncode
  except subprocess.TimeoutExpired:code=124
 results.append(dict(script=script,exit_code=code,elapsed=round(time.monotonic()-begun,3),parallel_preflight_outer_timeout=timeout*2,formal_timeout_unchanged=timeout))
 (folder/'preflight.json').write_text(json.dumps(dict(scope='Remaining real capture scripts after navigation;extra parallel preflight;not additional unique tests or substitute for formal full007',source_commit='bd1e9c5aff9d049d5b5d0bb339bf4bc5d135a2da',results=results),indent=2)+'\n')
 print(script,code,flush=True)
 if code:raise SystemExit(code)
print('All remaining capture scripts passed',len(results),flush=True)
