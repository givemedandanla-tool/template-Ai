# 當前：review-tool Illustrator 接口已實作，實機 Adobe 驗收待辦

指定 `feature/review-tool-v0.1.0`，本輪基底 `f0aaddd9dd87f76d9ea85853bfd633548906c942`；checkpoint `CP-20261025-REVIEW-ILLUSTRATOR-002`。先讀 [部件 STATE](windows_review_environment/illustrator-20261025/STATE.json)、[報告](windows_review_environment/illustrator-20261025/REPORT.md) 與 [接口指南](../../tools/windows_review_dev/illustrator_bridge/README.md)。使用者最新要求是在有 Illustrator 的 Windows 環境建立接口。

「更多」→「使用 Illustrator 匯入 AI（實驗性）」以選配 pywin32 311 呼叫本機 Illustrator，輸出新 PDF 來源；「停止等候 Illustrator」只停止自身 helper，遲到輸出不採用。原稿雜湊、全部畫板頁數及提示頁檢查通過才加入。原稿／既有文件與人工核對保留，不自動當作已核對。

Windows 最終 56 PASS／0 skip（接口 26、PDF 17、Jobs/UI 13），接口測試含 14 個合成 Adobe DOM 情境。此機無 Illustrator，真 host 回報 NOT_INSTALLED；真實原生 AI 轉 PDF／保真仍 NOT_VERIFIED。不要將合成結果升為 Adobe／私人文件／EXE 資格。

下一步：有 Illustrator 的機器依指南安裝選配 COM 套件並跑 smoke.py，以新短路徑建立兩畫板合成 AI，確認自動與人工目視結果，再測缺字型／連結、已有未保存文件及取消。原 Inkscape 原生 AI 擴充仍因文字遺失而未接入。DirectWrite 未重現；完整 OCR 未配置。

源碼仍 0.1.0-beta.3.dev1，既有 beta.2 發布不變。不合併 main、不打包發布，私人資料不上傳。依 [同步規則](windows_review_environment/SYNC_POLICY.md) 讀回；共享歷史 AGENTS／STATE／WORK_LOG 不更新。精確提交／收據以本部件 STATE 為準。
