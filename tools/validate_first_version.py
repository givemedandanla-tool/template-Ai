"""保存真實測試、Qt 畫面與數位輸出，提供可重現的研究版驗證憑證。"""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import argparse
import shutil
import copy
from dataclasses import asdict

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
from template_ai.model import Rect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true", help="由證據 runner 已執行具名測試後只生成 GUI／成品")
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    artifacts = args.artifacts_dir or root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    if not args.skip_tests:
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
        export(c, target, dpi=args.dpi)
    window = MainWindow(artifacts / ("anonymous-smoke-data-" + app_version))
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
        export(decorated, target, dpi=args.dpi)
    window.tabs.setCurrentIndex(0)
    multi_path = root / "examples/synthetic-two-artworks.svg"
    multi_source = window.library.add_source(multi_path, import_file(multi_path, window.library.assets))
    marked = {"crop": asdict(Rect(0, 0, 90, 54)), "work_width": 90, "work_height": 54,
              "slots": [asdict(slot) for slot in demo_template().slots], "visual_confirmed": False}
    first = window.library.create_artwork(multi_source["id"], "左側合成作品", marked)
    marked["crop"] = asdict(Rect(90, 0, 90, 54))
    second = window.library.create_artwork(multi_source["id"], "右側合成作品", marked)
    window.refresh_sources(multi_source["id"])
    app.processEvents()
    window.grab().save(str(artifacts / "multiple-artworks-workspace.png"))
    from template_ai.source_dialog import SourceRelinkDialog
    from template_ai.source_discovery import discover_sources
    search_root = window.library.root / "anonymous-candidate-sources"
    search_root.mkdir(exist_ok=True)
    shutil.copyfile(source_path, search_root / "renamed-synthetic.svg")
    sources = window.library.list_sources()
    for item in sources: item["impacts"] = window.library.source_impacts(item["id"])
    dialog = SourceRelinkDialog(window)
    dialog.resize(1500, 600)
    dialog.show_report(discover_sources(sources, search_root))
    dialog.show()
    app.processEvents()
    assert dialog.table.rowCount() == len(sources)
    assert all(not dialog.table.cellWidget(i, 0).isChecked() for i in range(len(sources)))
    if not dialog.grab().save(str(artifacts / "batch-source-preview.png")):
        raise ValueError("批次來源預覽截圖保存失敗")
    dialog.close()
    from template_ai.font_catalog import build_inventory,host_candidates,analyze_font
    from template_ai.font_dialog import FontCenterDialog
    environment_font = next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'),Path(r'C:\Windows\Fonts\arial.ttf')) if p.is_file()),None)
    if environment_font is None:
        raise ValueError("沒有環境可用字型，無法生成實際字型中心驗收附件")
    font_asset = window.font_manager.import_font(environment_font, approved=True)
    font_template = demo_template()
    font_template.name = "合成字型引用"
    font_template.source_id=multi_source["id"];font_template.source_work_id=first["id"];font_template.source_work_revision=first["revision"];font_template.artwork=Rect(0,0,90,54)
    for slot in font_template.slots:
        slot.font, slot.font_asset = font_asset["families"][0], dict(font_asset)
    window.library.save_template(font_template)
    hosts, partial = host_candidates()
    center = FontCenterDialog(window)
    center.show_inventory(build_inventory(window.library.fonts(),window.library.templates(),hosts,partial))
    center.resize(1500,900)
    center.show(); app.processEvents()
    if not center.grab().save(str(artifacts / "font-center-workspace.png")):
        raise ValueError("字型管理中心截圖保存失敗")
    center.kind.setCurrentIndex(center.kind.findData("ASSET")); center.table.selectRow(0)
    diagnosis = analyze_font(center.selected(),center.text.text(),center.size.value(),center.width.value(),center.minimum.value()/100)
    assert diagnosis["status"] == "FEASIBLE_WIDTH", diagnosis
    center.show_analysis(diagnosis); app.processEvents()
    if not center.grab().save(str(artifacts / "font-center-diagnostics.png")):
        raise ValueError("字形／毫米量測實際截圖保存失敗")
    from template_ai.font_candidate_dialog import FontCandidateDialog
    import time
    candidates = FontCandidateDialog(center)
    candidates.resize(1500,1000); candidates.compare.setChecked(True)
    candidates.show(); candidates.search_button.click()
    def wait_candidates():
        deadline=time.monotonic()+20
        while (candidates.busy or window.busy) and time.monotonic()<deadline:
            app.processEvents(); time.sleep(.005)
        if candidates.busy or window.busy: raise ValueError("候選真實背景工作未完成")
    wait_candidates()
    assert candidates.report and candidates.report["candidates"], candidates.status.text()
    assert candidates.selected() is None
    app.processEvents()
    if not candidates.grab().save(str(artifacts / "font-candidates-ranked.png")):
        raise ValueError("候選排名實際截圖保存失敗")
    candidates.table.selectRow(0); candidates.preview_button.click(); wait_candidates()
    assert candidates.preview_data, candidates.status.text()
    app.processEvents()
    if not candidates.grab().save(str(artifacts / "font-candidates-preview.png")):
        raise ValueError("候選唯讀預覽實際截圖保存失敗")
    (artifacts / "font-candidate-line.png").write_bytes(candidates.preview_data["png"])
    report=candidates.report
    summary={k:report[k] for k in ("status","input","reference_width_mm","reference_issue","checked_faces","omitted_faces","hidden_eligible","bytes_budgeted","scope")}
    summary["candidates"]=[{k:c[k] for k in ("rank","requested_style","analysis","source_priority","width_delta_ratio","reasons")} for c in report["candidates"]]
    summary["excluded"]=[{"families":c["row"]["families"],"style":c["requested_style"],"reasons":c["reasons"]} for c in report["excluded"]]
    (artifacts / "font-candidates-report.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    candidates.close()
    center.close()
    # 受控替代流程實際GUI／真正worker；只用合成模板與環境字型。
    from template_ai.font_review_dialog import FontReviewDialog
    from template_ai.font_review import field_key
    from PySide6.QtWidgets import QMessageBox
    from unittest.mock import patch
    mono_path=Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
    if not mono_path.is_file():raise ValueError('受控替代實際證據缺少另一環境字型')
    mono=window.font_manager.import_font(mono_path,approved=True)
    target=build_inventory([mono],[],[])['rows'][0]
    review=FontReviewDialog(window,target,'Alex Example');review.resize(1500,1040);review.show()
    def wait_review():
        deadline=time.monotonic()+20
        while (review.busy or window.busy) and time.monotonic()<deadline:
            app.processEvents();time.sleep(.005)
        if review.busy or window.busy:raise ValueError('受控替代背景工作未完成')
    row_index=next(i for i,r in enumerate(review.rows) if r['template']['id']==font_template.id and r['slot']['kind']=='name')
    review.table.selectRow(row_index);review.fill_selected();review.validate();wait_review()
    assert review.report and review.report['rows'][row_index]['eligible'],review.status.text()
    assert all(not review.table.cellWidget(i,0).isChecked() for i in range(review.table.rowCount()))
    if not review.grab().save(str(artifacts/'font-review-differences.png')):raise ValueError('差異GUI截圖失敗')
    from template_ai.comparison_view import CanvasCompareDialog
    def capture_compare(dialog):
        dialog.show();app.processEvents();dialog.fit_template();app.processEvents()
        assert dialog.data['source']['mapping']['revision']==first['revision']
        if not dialog.grab().save(str(artifacts/'canvas-compare-overview.png')):raise ValueError('完整三視圖截圖失敗')
        dialog.focus_selected();dialog.zoom(1.5);app.processEvents()
        if not dialog.grab().save(str(artifacts/'canvas-compare-focused.png')):raise ValueError('同步定位截圖失敗')
        for mode in ('source','before','after'):(artifacts/('canvas-compare-'+mode+'.png')).write_bytes(dialog.data[mode+'_png'])
        report={k:v for k,v in dialog.data.items() if not k.endswith('_png') and k!='files'}
        report['file_sha256']=list(dialog.data['files'].values())
        (artifacts/'canvas-compare-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        dialog.accept();return CanvasCompareDialog.Accepted
    with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes),patch.object(CanvasCompareDialog,'exec',capture_compare):
        review.table.selectRow(row_index);review.review_selected();wait_review()
        assert review.preview_data,review.status.text()
        if not review.grab().save(str(artifacts/'font-review-approved.png')):raise ValueError('逐欄審核GUI截圖失敗')
        review.table.cellWidget(row_index,0).setChecked(True);review.apply_selected();wait_review()
        assert review.records and review.records[0]['phase']=='APPLIED',review.status.text()
        record=review.records[0];created=record['drafts'][0]['template_id']
        assert next(t for t in window.library.templates() if t.id==font_template.id).to_dict()==font_template.to_dict()
        review.history.selectRow(0);app.processEvents()
        if not review.grab().save(str(artifacts/'font-review-draft-history.png')):raise ValueError('草稿／歷史GUI截圖失敗')
        review.history_action('UNDO');wait_review();assert review.records[0]['phase']=='UNDONE'
        if not review.grab().save(str(artifacts/'font-review-undone.png')):raise ValueError('Undo GUI截圖失敗')
        review.history.selectRow(0);review.history_action('REDO');wait_review();assert review.records[0]['phase']=='APPLIED'
    (artifacts/'font-review-audit.json').write_text(json.dumps(review.records[0],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    review.close()
    from template_ai.object_dialog import ObjectToolsDialog
    window.template=None;window.refresh_templates(created);window.tabs.setCurrentIndex(1)
    objects=ObjectToolsDialog(window,'TEMPLATE',created);objects.show();app.processEvents();objects.canvas.fit()
    object_ids=[s.id for s in window.template.slots[:2]];objects.select_ids(object_ids)
    if not objects.grab().save(str(artifacts/'object-tools-multiselect.png')):raise ValueError('多選GUI證據失敗')
    objects.editors['color'].setText('#224466');objects.preview_patch()
    if not objects.grab().save(str(artifacts/'object-tools-mixed-patch.png')):raise ValueError('dirty patch證據失敗')
    objects.invalidate();objects.reference.setCurrentIndex(objects.reference.findData(object_ids[0]));objects.direction.setCurrentIndex(1);objects.preview_geometry()
    # Different-width fixture is not needed for a real MOVE; all geometry fields stay fixed.
    objects.preview_request({'operation':'MOVE','ids':object_ids,'dx':1,'dy':1})
    assert objects.plan,objects.status.text();scope_report=copy.deepcopy(objects.plan)
    if not objects.grab().save(str(artifacts/'object-tools-difference.png')):raise ValueError('幾何候選證據失敗')
    with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
        objects.apply();assert objects.records,objects.status.text();objects.history.selectRow(0)
        if not objects.grab().save(str(artifacts/'object-tools-history.png')):raise ValueError('歷史GUI證據失敗')
        objects.history_action('UNDO');assert objects.records[0]['phase']=='UNDONE'
        objects.history.selectRow(0);objects.history_action('REDO');assert objects.records[0]['phase']=='APPLIED'
        objects.select_ids(object_ids);objects.preview_lock(True);objects.apply()
        assert all(s['locked'] for s in objects.snapshot['payload']['slots'] if s['id'] in object_ids)
        objects.select_ids(object_ids)
        if not objects.grab().save(str(artifacts/'object-tools-locked.png')):raise ValueError('鎖定GUI證據失敗')
    audit={'geometry_plan':scope_report,'history':objects.records,'template_before':font_template.to_dict(),'scope':'匿名／程序化明確核准，非真人獨立覆核；原字体／真實資料未上傳'}
    (artifacts/'object-tools-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');objects.close()
    source_objects=ObjectToolsDialog(window,'ARTWORK',first['id']);source_objects.show();app.processEvents();source_objects.canvas.fit()
    source_ids=[s['id'] for s in source_objects.snapshot['payload']['slots'][:2]];source_objects.select_ids(source_ids)
    source_objects.preview_request({'operation':'MOVE','ids':source_ids,'dx':1,'dy':1})
    assert source_objects.plan,source_objects.status.text()
    if not source_objects.grab().save(str(artifacts/'object-tools-training.png')):raise ValueError('來源模式證據失敗')
    source_objects.invalidate();source_objects.close()
    from capture_work_packages import capture_index,capture_batch
    capture_index(window,artifacts,first['id'],created)
    capture_batch(window,artifacts)
    window.close()
    reopened = MainWindow(artifacts / ("anonymous-smoke-data-" + app_version))
    assert reopened.work["id"] == second["id"]
    reopened.work_combo.setCurrentIndex(reopened.work_combo.findData(first["id"]))
    assert len(reopened.slots) == 4
    assert reopened.library.font_change_history()[0]['phase']=='APPLIED'
    assert next(t for t in reopened.library.templates() if t.id==created).slots[0].font_asset['hash']==mono['hash']
    reopened.close()
    files = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in artifacts.iterdir() if p.is_file() and p.name != "VALIDATION.json"}
    evidence = {"app_version": app_version, "python": platform.python_version(), "platform": platform.platform(), "PySide6": qt_version,
                "inkscape": inkscape_path(), "tests_exit_code": None if args.skip_tests else result.returncode, "files": files,
                "scope": "合成／匿名來源、實際 Inkscape 多頁轉換、Qt GUI、固定背景／文字色彩、多作品標記恢復、本機持久字型與新 Python 程序載入、來源與前後矩形同步唯讀對照、數位輸出；程式化核准並非真人視覺驗收",
                "not_verified": ["真實 Illustrator 私有樣本全面視覺驗收", "VivoBook／RTX 5050 效能", "實體印刷", "獨立審查"]}
    (artifacts / "VALIDATION.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"tests": "NOT_RUN_CAPTURE_ONLY" if args.skip_tests else "PASS", "captures": sum(name.endswith(".png") and not name.endswith("FINAL.png") for name in files), "exports": 6, "validation": str(artifacts / "VALIDATION.json")}))


if __name__ == "__main__":
    main()
