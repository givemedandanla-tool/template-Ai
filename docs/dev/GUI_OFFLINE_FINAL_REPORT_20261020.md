# 桌面工作台、進階引導與離線報告交付結果

本輪 CORE-090 的10條驗收全部通過自我驗證。三個桌面工作區已接正式核心，網頁／手機／EXE仍延後。這不是私人作品、Windows、指定設備、實體印刷或真人新手資格。

## 使用上改變

- 共用「排版與輸出」：填人物／公司資料→產生完整稿件→拖動或選單調整相對位置→更正→重新確認→儲存。沿用同一份資料、版本、家族與規則，不增加客戶字級／字寬／單雙排控制。
- 主預覽、固定主要動作與白話下一步；專業工具按需開啟。固定稿的唯讀摘要可見，必要候選可以直接點選；切頁與舊命令不丟工具狀態。
- 「匯入與學習」「模板與圖片」保留原有工具。工作引導提供來源核對、驗證案例、適合範圍與正式啟用審查；缺證據仍阻擋，合成案例不能冒充真實資格。
- 「問題與報告」手動輸出白話與技術雙層ZIP。最近320筆安全事件、1MiB封裝上限；版本、階段、缺資訊分類、錯誤類型／可信程式位置及可取得耗時／資源。原稿、輸入原文、字型、資料庫、任意例外文字與敏感路徑不進共享報告。
- 日常程式不自動連網／上傳。Python網路與遠端文件資源前置阻擋；這不是整台Windows或第三方原生程式的作業系統防火牆。首次安裝依賴與離線啟動分開。
- 接入3個專項skill、5個可重建agent角色，保留原UI/UX Pro Max與Qt Designer；來源／授權／hash在gui_tooling。團隊審查屬自我驗證。

## 驗證

正式來源：`4ebfff6f676b236519c4a1ba2b0cb192acbffea3`。完整[run](../../docs/evidence/runs/RUN-GUI-OFFLINE-ALL-006/run.json)：**1850／1850 PASS，236健康模組、0未處理例外、擷取exit0、397件附件雜湊核對**。原1798個測試ID全部保留，新增52；未刪除或放寬原失敗斷言。

原生xcb：桌面12／12＋原導航3／3；11張流程圖，另3頁自有視窗與Tab通過。原生與offscreen重複案例不累加進1850。原生owner264.935秒、600秒上限。開發中80a來源另保留三個舊擷取入口的37PNG／3metadata／1匿名PDF；它們不是最終來源證明。最終舊擷取入口由本輪完整run重新執行。

| 條款 | 驗收 | 結果 |
| --- | --- | --- |
| CORE-090-A01 | 全功能導航與保留 | PASS |
| CORE-090-A02 | 共用正式製作與拖動 | PASS |
| CORE-090-A03 | 版本與確認保護 | PASS |
| CORE-090-A04 | 白話狀態與鍵盤小視窗 | PASS |
| CORE-090-A05 | 進階真實服務引導 | PASS |
| CORE-090-A06 | 完全離線與安全本地日誌 | PASS |
| CORE-090-A07 | 手動安全診斷匯出 | PASS |
| CORE-090-A08 | 更多skill與agent接入 | PASS |
| CORE-090-A09 | 保留原測試並完整回歸 | PASS |
| CORE-090-A10 | 本地啟動與GitHub可恢復交付 | PASS |

詳細映射見[十條驗收](GUI_OFFLINE_10_CLAUSE_AUDIT_20261020.json)。額外114件GUI工具／skill逐檔與凍結Git樹核對，前後一致；兩個Windows啟動腳本已納入正式code manifest與checkpoint。

完整run的整體狀態仍為`FAIL`：僅原有5條外部／延後資格未滿足，與前一接受來源相同；軟體執行狀態為PASS。未以GUI自驗替代它們。

## 保留失敗紀錄

- ALL001：241完成239PASS／2FAIL後中斷，修定位屬性、收合停用候選；另外修hidden TabBar焦點陷阱。
- ALL002：1849完成1845PASS／4FAIL、9次已刪Qt計時器例外，來源一致，未採用。修預檢返回、圖片狀態查詢、舊收合命令、固定稿摘要／候選及銷毀訊號；target21及fresh75通過。
- ALL003：root預先建立補充證明目錄，unique-ID防護正確拒絕，0測試執行；保留啟動紀錄，改新ID，不覆寫。
- ALL004：781／781PASS時主動中斷，人工發現help過時與預覽控制不夠直接；修正並保留原生003舊來源證據。
- 目標005同程序15項有1項原候選計數失敗（早於新增縮放斷言），診斷觀察GUI與fresh-thread取得不同字面，而fresh-thread依賴吻合worker保存值；snapshot Gate正確阻擋（原worker字面未直接插樁）；既有正式fresh-module目標00615／15PASS，原斷言不變，不宣稱跨字型環境資格。
- ALL005：572／572PASS時因1次Qt eventFilter型別例外中斷；三個observer補型別與有效性守衛，原測試增強，fresh41／41PASS／0runtime。
- ALL006：本輪正式採用。
- WIP1：錯誤base SHA的checkpoint metadata已棄用；原來源Git讀回保留，後續WIP2／3／4採實際HEAD並逐檔確認。原生中斷／工具前提失敗亦保留，不冒充PASS。

## 完成數與後續

172筆登錄中，父題75：69已驗證、3部分（UI-032, REV-02, REV-04）、3延後（UI-048, UI-056-D, REV-03）；CORE90／90及GOV7／7為明列範圍已驗證。相對本輪前基準只新增CORE-090一筆，不把驗收或測試數當父題數。原AI8包50條完整真實資格仍8部分／0完整，四類暫擱維持使用者決定。

本地操作：[快速開始](LOCAL_DESKTOP_QUICK_START.md) → [桌面指南](DESKTOP_WORKSPACE_USER_GUIDE_20261020.md) → [離線報告](OFFLINE_SUPPORT_USER_GUIDE_20261020.md)。首次明確執行PREPARE_WINDOWS.bat，之後START_WINDOWS.bat離線啟動。私人資料先另行備份；報告由使用者手動提供Codex，沒有自動傳送。

GitHub保存使用既有`dev/v0.1-first-version`／PR2，不合併main。最終checkpoint收據以STATE為準；新對話讀AGENTS→STATE→ACTIVE_DEVELOPMENT_HANDOFF，執行resume_status即可接續。

最終保存：`CP-20261020-GUI-OFFLINE-FINAL` 已REMOTE_VERIFIED，來源、測試、397件公開附件及全部本輪報告已精確Git讀回。嚴格`--require-evidence`與核准範圍檢查皆PASS（172登錄、166明列範圍完成）；不新增證據豁免。見[治理結果](../qa/targeted/GUI-FINAL-GOVERNANCE.json)及STATE最新收據。後續收據／環境草稿metadata commit不修改已驗證程式。
