# 證明附件上傳優先序修正

使用者後續明確指令：「如果這只是證明文件就略過，持久化在GIHUB文件中就好，已開發速度為首要目標」。此指令優先於本輪先前要求反覆補齊全部二進位證據的工作方式。

本次採用範圍：停止重試尚未成功保存的9件證明附件，檔名、bytes、SHA-256／Git blob SHA、事件與解法持久化在 `docs/dev/EVIDENCE_PUBLICATION_EXCEPTIONS.json`、`COPYRIGHT_PRIVACY_EVENTS.md`。它們是最新run的重複GUI／數位輸出證明，不是未實作程式；原檔、原60件附件manifest與測試失敗紀錄保留，不換通道、轉藏內容或重新生成來避開審查。

功能與驗收條件不變：CORE040..045三包全部實作、真Qt流程、229項PASS／零SKIP；來源commit192db957不變。代碼、測試、JUnit、具名claims、來源／環境與已接受的GUI證據繼續保存。第一／第二包的完整歷史49／54件永久證據不受影響；最新run預計51／60件附件可讀，9件有明確未上傳狀態。

新的checkpoint明示保存範圍：全部code／tests／docs與已接受證據，僅排除上述9件上傳例外。使用乾淨staging view及原有prepare／ack工具核對實際檔案；不覆寫舊checkpoint，不把被排除附件計為已讀回。舊完整本機恢復ZIP仍包含全部原附件。

`dev_governance.py check`仍核對未改動的全部本機驗收與來源，必須PASS。舊 `--require-evidence` 的「全部60附件永久保存」Gate維持未滿足，不能宣稱PASS；這項公開保存例外與SELF_VERIFIED功能完成分開記錄。Windows、真實AI全面視覺、指定硬體及獨立覆核仍未驗，75父需求不冒稱完整。

後續以功能開發為先，不因這些證明附件反覆問答或停頓。若日後另有完整附件交付需求，先確認具名binary API與具體風險核對能力，再做獨立保存工作，不重做已驗程式。
