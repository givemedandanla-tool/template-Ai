"""Apply ONLY after LAYOUT002 fully exits; preserve waits and real resource tests."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
F=ROOT/'docs/evidence/runs/RUN-REMAINING28-LAYOUT-002'
assert (ROOT/'docs/qa/targeted/remaining28-layout-002-parent-exit.txt').read_text().strip()=='1'
run=json.loads((F/'run.json').read_text());assert run['status']=='FAIL' and run['source_unchanged']
p=ROOT/'tests/gui_wait.py';s=p.read_text();assert 'def job_diagnostics' not in s
s+='''\n\ndef job_diagnostics(window,kind='ANALYSIS'):
    if window is None:return 'No owned GUI window recorded'
    decision=window.runtime.admit(kind,foreground=True)
    return str(dict(status=window.statusBar().currentMessage(),allowed=decision.allowed,reasons=list(decision.reasons),active_threads=window.pool.activeThreadCount(),waiting_launches=len(window._waiting_launches),owned_jobs=len(window._background_jobs),policy_error=window.runtime.policy_error,library_closed=window.library.closed))
''';p.write_text(s)
p=ROOT/'tests/test_output_batch_gui.py';s=p.read_text();assert 'controlled_resources(window)' not in s;s=s.replace('APP=fixture.APP','APP=fixture.APP\nfrom runtime_fixture import controlled_resources\nfrom gui_wait import job_diagnostics');s=s.replace('window=MainWindow(self.library.root);self.addCleanup','window=MainWindow(self.library.root);controlled_resources(window);self.addCleanup');s=s.replace("self.fail('output worker did not finish within bounded test wait')","self.fail('output worker did not finish within bounded test wait: '+job_diagnostics(d.window,'EXPORT')+'; dialog='+d.status.text())");p.write_text(s)
p=ROOT/'tests/test_automatic_training.py';s=p.read_text();assert 'self._gui_wait_window' not in s;s=s.replace('self.addCleanup(close);return window','self.addCleanup(close);self._gui_wait_window=window;return window');s=s.replace("        self.fail('Actual background workflow did not finish')", "        from gui_wait import job_diagnostics\n        self.fail('Actual background workflow did not finish: '+job_diagnostics(getattr(self,'_gui_wait_window',None)))");p.write_text(s)
print('Added bounded failure diagnostics and controlled output-workflow fixture; unchanged wait limits/real pressure tests. Startup root cause not claimed fixed.')
