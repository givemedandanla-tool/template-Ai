"""一次性保留原 75 筆要求，補精確 CORE 驗收；既有登錄存在時拒絕覆寫。"""
from pathlib import Path
import csv

from dev_common import ROOT, write_json


def main():
    target = ROOT / "docs/dev/REQUIREMENTS.json"
    if target.exists():
        raise FileExistsError("要求登錄已存在，不能重新 bootstrap 覆蓋進度")
    rows = []
    with (ROOT / "docs/UI_FEATURE_INVENTORY.csv").open(encoding="utf-8", newline="") as file:
        for item in csv.DictReader(file):
            identity = item["決策編號"]
            deferred = identity in ("UI-056-D", "UI-048", "REV-03")
            blocked = identity in ("UI-066-R1", "UI-066-R2")
            status = "DEFERRED" if deferred else "BLOCKED" if blocked else "PARTIAL" if "部分" in item["實作狀態"] else "NOT_IMPLEMENTED"
            scope = item["關鍵驗收"]
            if identity == "UI-048":
                scope = "核心功能完善後最後接入；正式真實個資使用前必須完成"
            if identity == "UI-058":
                status = "NOT_IMPLEMENTED"
                scope += "；既有標記歷史是 UI-038 子能力，不能充當當次排版候選恢復已完成"
            rows.append({"id": identity, "kind": "topic", "title": item["功能主題"], "status": status,
                "completed": False, "review_level": "NOT_REVIEWED", "scope": scope, "phase": item["建議階段"],
                "decision_status": item["需求狀態"], "sources": [item["來源"]], "parents": [], "evidence_run": None,
                "acceptance": [{"id": identity + "-FULL", "expected": "完成來源文件中的全部已核准要求；以下為索引摘要：" + item["關鍵驗收"], "tests": []}],
                "next_step": "依來源拆分尚未完成的驗收子條件；不得用已做子集標完整主題完成"})
    definitions = [
        ("CORE-001", "固定字級與長文字無解阻擋", ["UI-013", "UI-014"], "test_first_version.FirstVersionTests", ["fixed_size_long_text_is_blocked_without_mutation"], "不改字級／不截斷長文字，無解時阻擋正式輸出"),
        ("CORE-002", "資料完整映射與人物容量", ["UI-015", "UI-016"], "test_first_version.FirstVersionTests", ["unused_contact_and_wrong_capacity_block"], "多筆聯絡或人物容量不符時明確阻擋，不默默略去"),
        ("CORE-003", "缺字型與幾何檢查", ["UI-031", "UI-012"], "test_first_version.FirstVersionTests", ["missing_font_does_not_use_silent_fallback", "geometric_overlap_and_outside_block_publication"], "指定字型缺失、超界及重疊不能通過正式發布／輸出"),
        ("CORE-004", "人物公司與同尺寸 Logo 防混配", ["UI-017", "UI-023", "UI-025"], "test_first_version.FirstVersionTests", ["missing_logo_and_wrong_size_or_company_do_not_pass", "person_company_binding_is_not_inferred_from_strings"], "公司歸屬明確；缺 Logo 或不同公司／尺寸不得借用正式輸出"),
        ("CORE-005", "數位三格式尺寸與安全寫檔", ["UI-019", "UI-029", "UI-030"], "test_first_version.FirstVersionTests", ["export_all_formats_real_pdf_dimensions_and_no_overwrite", "atomic_publish_failure_preserves_existing_file_and_cleans_temp"], "實際 PDF／PNG／JPG 可讀，PDF 毫米正確，既有檔及失敗清理保護"),
        ("CORE-006", "候選過期與非正式預覽標示", ["UI-028", "UI-059"], "test_first_version.FirstVersionTests", ["stale_generation_and_unmarked_preview_block", "gui_real_demo_flow_and_readonly_published_canvas"], "修改資料使舊候選失效；PREVIEW 有檔名及畫面附註"),
        ("CORE-007", "模板發布歷史不可覆寫", ["UI-010"], "test_first_version.FirstVersionTests", ["published_templates_are_immutable_and_family_versions_safe"], "已發布版本唯讀，新版本不占用已存在的 family/version"),
        ("CORE-008", "同內容快取與獨立來源登錄", ["UI-003", "UI-042"], "test_first_version.FirstVersionTests", ["source_dedupe_preserves_independent_registrations_and_reopen"], "同內容共用解析，異名登錄及標記不混配，重開恢復"),
        ("CORE-009", "人工標記規則模板閉環", ["UI-007", "REV-01"], "test_first_version.FirstVersionTests", ["source_labels_to_learned_template_to_output"], "標記形成有來源規則模板，發布、同尺寸配對與數位輸出可完成"),
        ("CORE-010", "Inkscape SVG 與 PDF 相容 AI", ["REV-02"], "test_first_version.FirstVersionTests", ["actual_inkscape_svg_and_pdf_compatible_ai"], "實際 SVG 轉換與合成 PDF 更名 AI 可匯入；不代表私人原生 AI 全面驗收"),
        ("CORE-011", "多頁 PDF 正確頁與備援", ["REV-02"], "test_import_pages.ImportPageTests", ["actual_second_page_and_cache_stay_distinct", "bad_pdf_page_is_rejected_before_converter_runs", "qt_fallback_really_selects_second_page", "non_pdf_page_is_explicitly_rejected"], "雙色頁實際取到指定頁、快取不混頁；非法頁碼在轉換前失敗"),
        ("CORE-012", "匯入前像素預算", ["UI-051"], "test_import_pages.ImportPageTests", ["extreme_svg_is_blocked_before_large_preview", "raster_budget_checks_header_before_decoding"], "極端比例／超大圖片先被阻擋，再配置畫面或解碼"),
        ("CORE-013", "固定背景實際向量與圖像輸出", ["UI-019", "UI-034"], "test_visual_background.VisualBackgroundTests", ["decoration_in_preview_and_all_actual_exports", "raster_choice_uses_approved_imported_pixels"], "預覽及三格式讀回有裝飾，向量／圖像模式均生效"),
        ("CORE-014", "背景核准、内容与失聯保護", ["UI-034"], "test_visual_background.VisualBackgroundTests", ["unapproved_and_wrong_size_background_block_publication", "changed_background_after_candidate_blocks_and_cleans_export", "missing_background_is_not_silently_rendered_white", "external_svg_resource_is_rejected_before_approval"], "未核准／錯尺寸／異動／失聯／外連資源不可冒稱有效背景"),
        ("CORE-015", "背景 GUI 核對及版本保護", ["UI-010", "UI-034"], "test_visual_background.VisualBackgroundTests", ["gui_background_controls_respect_published_version", "real_background_review_dialog_saves_chosen_mode", "reopen_version_and_old_schema_preserve_background"], "真實核准對話框保存呈現方式，發布背景版本唯讀，舊格式相容"),
        ("CORE-016", "人工文字色彩", ["UI-034"], "test_visual_background.VisualBackgroundTests", ["text_color_is_real_rendered_and_invalid_color_blocks"], "指定文字色彩確實渲染；非法色彩阻擋"),
        ("CORE-017", "多作品與上次來源上下文", ["UI-038", "UI-002"], "test_artwork_recovery.ArtworkRecoveryTests", ["two_works_reopen_active_selection_and_marks", "gui_new_crop_keeps_previous_work_and_reopens_latest", "gui_reopens_last_selected_source_not_latest_import"], "多作品獨立保存，切換／重開回到確切來源與作品"),
        ("CORE-018", "標記歷史、遷移與競爭寫入", ["UI-038", "UI-042"], "test_artwork_recovery.ArtworkRecoveryTests", ["history_restore_adds_revision_and_stale_update_blocks", "old_labels_migrate_once_without_deleting_legacy", "cross_source_selection_and_invalid_geometry_do_not_mutate", "gui_restore_history_preserves_published_template"], "恢復加新版本、不改歷史，舊資料保留，過期及跨來源寫入阻擋"),
        ("CORE-019", "模板固定學習來源版次", ["UI-007", "UI-055"], "test_artwork_recovery.ArtworkRecoveryTests", ["learned_template_pins_work_revision_and_rejects_wrong_source", "gui_learning_saves_exact_current_mark_revision"], "來源作品／版次固定，後改標記不改來源，不混配來源 ID"),
        ("CORE-020", "發布與審核同一交易", ["UI-010"], "test_artwork_recovery.ArtworkRecoveryTests", ["publish_event_failure_rolls_back_database_and_memory"], "模擬審核寫入失敗，資料庫與畫面仍是草稿"),
        ("CORE-021", "字型持久複本與新程序載入", ["UI-032"], "test_persistent_fonts.PersistentFontTests", ["copy_reopen_and_original_removal_do_not_lose_font", "new_python_process_loads_persisted_font", "gui_import_binds_file_and_reopens_without_dialog"], "本機複本可在新 Python 程序載入，欄位綁定資產持久保存"),
        ("CORE-022", "字型核准、異動與失敗保護", ["UI-032", "UI-033"], "test_persistent_fonts.PersistentFontTests", ["unapproved_invalid_and_duplicate_font_protect_catalog", "changed_or_missing_asset_blocks_even_if_system_font_exists", "same_family_different_file_is_not_silently_replaced", "catalog_failure_removes_only_new_asset"], "未核准、損壞、異動、同名不同檔明確阻擋，登錄失敗不留假資產"),
    ]
    for identity, title, parents, module, methods, expected in definitions:
        rows.append({"id": identity, "kind": "core", "title": title, "parents": parents, "status": "IMPLEMENTED_UNVERIFIED",
            "completed": False, "review_level": "NOT_REVIEWED", "scope": "Linux／合成或環境字型的明列子範圍；完整父要求仍待續", "phase": "P1～P3 子集",
            "decision_status": "既有核准要求的驗收子集", "sources": ["docs/FIRST_VERSION_STATUS.md"], "evidence_run": None,
            "acceptance": [{"id": identity + "-A1", "expected": expected, "tests": [module + ".test_" + method for method in methods]}],
            "next_step": "執行具名驗收並提交結構化證據；不擴大平台或資料範圍"})
    rows.append({"id": "CORE-023", "kind": "core", "title": "來源快取完整性與損壞恢復", "parents": ["UI-049", "UI-042"],
        "status": "NOT_IMPLEMENTED", "completed": False, "review_level": "NOT_REVIEWED", "scope": "本機衍生快取的內容驗證，非完整批次来源重連", "phase": "P1、P2",
        "decision_status": "既有核准要求子集", "sources": ["docs/DEVELOPMENT_PLAN.md"], "evidence_run": None,
        "acceptance": [{"id": "CORE-023-A1", "expected": "同來源快取經 hash 核對；異動／損壞 metadata 不可當成功重用；保持原檔只讀並可重新轉換", "tests": []}],
        "next_step": "框架 READY checkpoint 完成後，先補錯誤快取驗收，再修改 importer"})
    governance = [
        ("GOV-001", "開發 checkpoint 與安全恢復", ["checkpoint_restore_and_remote_ack", "checkpoint_rejects_mismatched_remote_and_existing_id"]),
        ("GOV-002", "Human／GPT 開工交接與下一步", ["missing_entry_blocks_work"]),
        ("GOV-003", "要求與個別證據完成 Gate", ["skipped_or_missing_test_cannot_complete", "changed_source_and_attachment_invalidate_evidence"]),
        ("GOV-004", "持久 AI 入口与零例行問答", ["missing_entry_blocks_work"]),
        ("GOV-005", "EXE 延後且不自動打包", ["automatic_exe_trigger_is_rejected"]),
    ]
    for identity, title, tests in governance:
        rows.append({"id": identity, "kind": "governance", "title": title, "parents": [], "status": "IMPLEMENTED_UNVERIFIED",
            "completed": False, "review_level": "NOT_REVIEWED", "scope": "本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔",
            "phase": "先於後續產品功能", "decision_status": "本輪使用者核准", "sources": ["docs/decisions/2026-10-13-CHECKPOINT-EVIDENCE-POLICY.md"], "evidence_run": None,
            "acceptance": [{"id": identity + "-A1", "expected": title + "的約定與有效性檢查通過", "tests": ["test_dev_framework.DevFrameworkTests.test_" + test for test in tests]}],
            "next_step": "本輪框架實際驗證後才能開下一產品工作包"})
    write_json(target, {"schema_version": 1, "registry_policy": "保留全部原題目；明列子範圍驗收，父需求不自動完成", "requirements": rows})
    print(f"Created {len(rows)} requirements (75 original topics, 23 CORE, 5 governance)")


if __name__ == "__main__":
    main()
