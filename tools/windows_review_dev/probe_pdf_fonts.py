"""Synthetic Qt/font/PDF probe; raw Qt messages remain in the chosen local dir."""
import argparse
import bdb
import inspect
import json
import os
from pathlib import Path
import sys

p = argparse.ArgumentParser()
p.add_argument('--root', required=True)
p.add_argument('--output', required=True)
p.add_argument('--integrated', action='store_true')
args = p.parse_args()
root = Path(args.root).resolve()
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=False)
sys.path[:0] = [str(root), str(root / 'tests')]
os.chdir(root)
from PySide6.QtCore import qInstallMessageHandler, qWarning
messages = []
def baseline_handler(kind, context, message):
    messages.append({'type': int(kind), 'message': message})
diagnostic = None
if args.integrated:
    from template_ai.review_tool.diagnostics import start_diagnostics
    diagnostic = start_diagnostics(out / 'diagnostics', role='probe')
else:
    previous = qInstallMessageHandler(baseline_handler)
qWarning('REVIEW_DIAGNOSTIC_CANARY_SYNTHETIC')
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QTextEdit, QVBoxLayout, QWidget
app = QApplication([])
from template_ai.review_tool.ui_font import configure_ui_font
configure_ui_font(app)
window = QWidget()
layout = QVBoxLayout(window)
layout.addWidget(QLabel('合成作品／更多／重新儲存 Adobe Illustrator PDF 123'))
layout.addWidget(QTextEdit('Synthetic artwork\n繁體中文 簡體中文 English 123'))
menu = QMenu(window)
menu.addAction('更多／匯出安全報告')
window.resize(640, 320)
window.show()
menu.popup(window.mapToGlobal(window.rect().center()))
app.processEvents()
window.grab().save(str(out / 'synthetic-ui.local.png'))
menu.close()
from test_review_source_compatibility import ReviewSourceCompatibilityTests, ENGLISH, TRADITIONAL
from template_ai.review_tool import source_compatibility as sc
from template_ai.review_tool.analysis import analyse_file
case = ReviewSourceCompatibilityTests()
case.root = out
observations = []
line = inspect.getsourcelines(sc.visible_pdf_page)[1] + next(
    n for n, text in enumerate(inspect.getsourcelines(sc.visible_pdf_page)[0])
    if "return {'page_count': count, 'language': placeholder_language(text)}" in text)
class ProbeDebugger(bdb.Bdb):
    def user_line(self, frame):
        if frame.f_code.co_filename == sc.__file__ and frame.f_lineno == line:
            local = frame.f_locals
            observations.append({'breakpoint': 'visible_pdf_page:classification',
                                 'line': line, 'page': local['page'],
                                 'page_count': local['count'],
                                 'visible_characters': len(local['text']),
                                 'language': sc.placeholder_language(local['text'])})
        self.set_continue()
debugger = ProbeDebugger()
assert debugger.set_break(sc.__file__, line) is None
rows = []
for name, content, expected in [('english', ENGLISH, 'en'), ('traditional', TRADITIONAL, 'zh-Hant'),
                                ('normal', 'Adobe Illustrator designer alice@example.com', None)]:
    path = case.pdf([content], name=name + '.ai')
    observed = debugger.runcall(sc.visible_pdf_page, path, 1)
    row = {'fixture': name, 'language': observed['language'], 'expected': expected,
           'classification_pass': observed['language'] == expected}
    if expected and row['classification_pass']:
        try:
            analyse_file(path, out / (name + '-cache'), ocr=False)
        except sc.ReviewSourceCompatibilityError:
            row['real_analysis_notice_rejected'] = True
    rows.append(row)
window.close()
app.processEvents()
if diagnostic:
    diagnostic.close()
    messages = [json.loads(s) for s in diagnostic.path.read_text(encoding='utf-8').splitlines()
                if json.loads(s).get('event') == 'qt_message']
else:
    qInstallMessageHandler(previous)
    (out / 'raw-messages.local.json').write_text(json.dumps(messages, ensure_ascii=False), encoding='utf-8')
texts = [m['message'] for m in messages]
summary = {'platform': app.platformName(), 'synthetic_only': True, 'integrated': args.integrated,
           'canary_count': sum(t == 'REVIEW_DIAGNOSTIC_CANARY_SYNTHETIC' for t in texts),
           'directwrite_count': sum('directwrite' in t.casefold() or 'dwrite' in t.casefold() for t in texts),
           'font_warning_count': sum('font' in t.casefold() for t in texts),
           'other_message_count': sum(t != 'REVIEW_DIAGNOSTIC_CANARY_SYNTHETIC' for t in texts),
           'breakpoints': observations, 'pdf_cases': rows, 'private_text_paths_fonts_in_summary': False}
(out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
raise SystemExit(0 if summary['canary_count'] == 1 and len(observations) >= 3 and all(r['classification_pass'] for r in rows) else 1)
