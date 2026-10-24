# 當前：OCR beta.2第四輪Windows驗證

精確source9fd9d9db720c83b5666b1de74dd7f4c5671e0b65／run40055712702。使用者授權隨包OCR並再次發布，beta.2未發布，beta.1保留。

最新IO修正：PNG原bytes由Python二進位fd送Tesseract stdin stdout，先釋放QImageReader；固定modeldir作cwd／--tessdata-dir .，保留pixels、psm、模型、原中文條件及timeouts。analysis10＋Logo6＋resolver15＋obsunit16＋GUI8全部PASS（真GUI35checks6.891秒），新增>320字含中文image／model路徑真辨識與bounds/原bytes保護。frozen＋package proof強制STDIN_BINARY_IMAGE。

第三run40054323702/c46aaaa4：261項260PASS/1FAIL/0skip/error/timeout，PDF問題已過；兩媒體均OCR_FAILED，CLI重播exit1無fields，runtime/modelhash/version全正確。影像路徑推算258短名→261長名有WinMAX_PATH風險，尚須當輪before/after證據。新增diagnostic只固定合成白名單，記錄legacy filename與stdin兩種replay stderr／words/bboxes/path長度/Unicode、version/modelhash；不將重播當releaseproof。

若第四輪仍FAIL，讀review-release-evidence/v0.1.0-beta.2/runs/40055712702-1-9fd9d9db720c/source-tests/test_review_tool_gui.log的ASCIIJSON。來源先全PASS→真正EXE包內雙語雙媒體＋實體缺壞人工退路→原private payload gate→六附件草稿與公開兩次下載逐檔/來源ZIP內檔校驗→finalcheckpoint/nativeGit讀回才交付。

source25archives260799778bytes及75notices已精確固定，runtime107entries+manifest108files，模型單份engines/ocr-models；源碼附件另附。第一run缺被build忽略的zstd/build/LICENSE已固定追蹤75/75；第二runPDF暫存handle已改QBuffer通過；GitHub401已恢復。原失敗證據在版本目錄，所有source已推feature/exactrequest。main、私有作品／DB／模型、原未提交timeout/adopt工作不變；無新付費API或資源。
