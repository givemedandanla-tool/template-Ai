"""保存真實測試、Qt 畫面與數位輸出，提供可重現的研究版驗證憑證。"""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6 import __version__ as qt_version
from PySide6.QtWidgets import QApplication
from template_ai.demo import demo_template
from template_ai import __version__ as app_version
from template_ai.background import make_background
from template_ai.gui import MainWindow
from template_ai.importer import import_file, inkscape_path
from template_ai.layout import generate
from template_ai.render import export


def main():
    root = Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=root,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    (artifacts / "TEST_RESULTS.txt").write_text(result.stdout+result.stderr, encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)
    app = QApplication.instance() or QApplication([])
    t = demo_template()
    t.state = "published"
    data = [{"name": "林小明", "title": "設計顧問", "phone": "0900-123-456", "email": "hello@example.test"}]
    c = generate(t, data, [], {})
    assert c.valid, c.issues
    for extension in ["png", "pdf", "jpg"]:
        target = artifacts / ("synthetic-FINAL."+extension)
        # 僅清理本工具的合成產物，應用程式不使用這個覆寫方式。
        target.unlink(missing_ok=True)
        export(c, target)
    window = MainWindow(artifacts / "anonymous-smoke-data")
    window.add_demo()
    window.library.publish(window.template)
    window.refresh_templates(window.template.id)
    window.tabs.setCurrentIndex(2)
    window.demo_input()
    window.generate()
    window.show()
    app.processEvents()
    window.output_canvas.fit()
    app.processEvents()
    assert window.candidates[0].valid
    window.grab().save(str(artifacts / "output-workspace.png"))
    window.tabs.setCurrentIndex(0)
    source_path = root / "examples/synthetic-source.svg"
    source = window.library.add_source(source_path, import_file(source_path, window.library.assets))
    window.refresh_sources(source["id"])
    window.slots = demo_template().slots
    window.refresh_training()
    window.train_canvas.fit()
    app.processEvents()
    window.grab().save(str(artifacts / "training-workspace.png"))
    # 固定背景核准只使用合成樣本，不能代替真人的原稿視覺驗收。
    window.tabs.setCurrentIndex(1)
    window.new_version()
    background = import_file(root / "examples/synthetic-background.svg", window.library.assets)
    window.template.background = make_background(background, 90, 54, approved=True)
    window.template.slots[0].color = "#173d75"
    window.library.save_template(window.template)
    window.library.publish(window.template)
    decorated_id = window.template.id
    window.refresh_templates(decorated_id)
    window.edit_canvas.fit()
    app.processEvents()
    window.grab().save(str(artifacts / "template-workspace.png"))
    window.tabs.setCurrentIndex(2)
    window.generate()
    decorated = next(c for c in window.candidates if c.template.id == decorated_id)
    assert decorated.valid, decorated.issues
    window.candidate_list.setCurrentRow(window.candidates.index(decorated))
    app.processEvents()
    window.grab().save(str(artifacts / "decorated-output-workspace.png"))
    for extension in ["png", "pdf", "jpg"]:
        target = artifacts / ("decorated-FINAL." + extension)
        target.unlink(missing_ok=True)
        export(decorated, target)
    window.close()
    files = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in artifacts.iterdir() if p.is_file() and p.name != "VALIDATION.json"}
    evidence = {"app_version": app_version, "python": platform.python_version(), "platform": platform.platform(), "PySide6": qt_version,
                "inkscape": inkscape_path(), "tests_exit_code": result.returncode, "files": files,
                "scope": "合成／匿名來源、實際 Inkscape 多頁轉換、Qt GUI、固定背景與文字色彩、數位輸出；合成背景程式化核准並非真人視覺驗收",
                "not_verified": ["真實 Illustrator 私有樣本全面視覺驗收", "VivoBook／RTX 5050 效能", "實體印刷", "獨立審查"]}
    (artifacts / "VALIDATION.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"tests": "PASS", "captures": 4, "exports": 6, "validation": str(artifacts / "VALIDATION.json")}))


if __name__ == "__main__":
    main()
