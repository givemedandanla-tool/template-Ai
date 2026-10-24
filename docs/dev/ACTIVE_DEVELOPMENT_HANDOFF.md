# 當前：新增隨包OCR並發review-v0.1.0-beta.2

使用者已授權「加入ocr執行器，然後再次發佈」。版本增為0.1.0-beta.2；beta.1已發布不可覆寫。讀STATE.review_tool_release_request與releases/review-v0.1.0-beta.2/IMPLEMENTATION_AND_VALIDATION_PLAN.md。

先固定可信Windows OCR包／hash／授權，再連接包內優先／損壞明示；模型維持engines/ocr-models，執行器engines/tesseract。真正EXE在沒有預裝OCR的環境必須成功辨識英文與繁中，再做原發布包及雙下載gate。未通過不得稱已發布。

既有相關16模組保留，另加runtime／builder／OCR相依測試；舊產品資格／main／原未提交timeout/adopt工作不變。私人作品仍本機，無付費API／新雲端服務。beta.1交接已歸檔PREVIOUS_RELEASE_HANDOFF.md。
