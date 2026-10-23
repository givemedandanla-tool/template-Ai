# 已採用：修正版發佈速度與驗證快取

2026-10-23使用者已授權建置。適用既有免費能力與標準公開Windows runner，不新增產品功能或本次新版本發佈，不覆寫beta.1／beta.2。原[發佈維護規則](../RELEASE_MAINTENANCE_POLICY.md)仍適用，本頁補充工程流程。

## 快取規則

- `.github/windows-wheels-lock.json`固定現有27個Windows cp311/x64 wheel版本、官方URL、大小與SHA，及需求檔hash。逐檔驗證後以`--no-index --require-hashes --no-deps`離線安裝並`pip check`，日常不解析最新版。
- `.github/release-assets-lock.json`綁定beta.2已公開資產。只從固定ZIP取出11837份Inkscape元件；不重用舊TemplateAI.exe。pin、來源map、聲明、完整清單及每檔hash全驗，拒絕額外檔／符號連結／路徑越界。新產品仍乾淨PyInstaller建置，不快取venv、測試資料、模型、整個workspace或舊成品。vendor每檔bytes／SHA保持精確；原Windows生成的CRLF來源JSON與Git LF lock另以解析內容比對，不把合法換行差異當工具版本改變。
- 未改元件時重用同一份來源ZIP，仍用原125來源物件驗證器核對。新Release的說明、manifest及SOURCE_DOWNLOADS.json清楚連結原公開ZIP；不必每版再上傳相同908MB。原引擎散佈檔保留首次beta.2原始bytes，後續來源位置以上述明確連結為準。元件／鎖檔／授權內容變更須重新審查pin，不能改hash求過關。
- key綁定平台、Python完整版本與完整鎖檔內容。命中只代表輸入可重用，不代表測試通過；每次再驗hash。一般損壞可重新取得，異常檔案型別或多出檔案停止，最多3次下載，不放寬TLS／完整性。
- 只用GitHub標準免費cache，先讀使用量、要求公開repo；既有用量須≤8GiB且本cache≤2GiB，保留10GiB預設內的餘裕。無法確認時不新增cache，繼續已驗證公開附件／本地重用。不修改quota、帳務或刪別人的cache。Actions版本也固定commit。輸入、安裝與工具guard通過後就保存，產品仍未驗收；後續產品失敗不抹去已驗證輸入。續接build須同一source commit及INPUTS_VERIFIED狀態，並再次驗輸入。

## 修改影響與不可省略項

工具`release_impact.py`對基底與HEAD建反向import圖聯集，保留刪除的舊呼叫邊；O(V+E)求可達性。穩定的snapshot動態載入由雜湊綁定契約補邊，檔案改變或未知載入就擴大。沒有導入coverage context學習索引；不能把靜態圖當所有行為的完備證明。

| 修改 | 執行規則 |
| --- | --- |
| 純文件 | 可不產新EXE；明確要求建置時仍完整Windows檢查。 |
| 有已知測試關聯的非核心模組 | 受影響Windows模組＋固定8模組底線；另列全部受影響來源模組。 |
| 資料／學習／核心／字型／輸出、入口、打包、工具鏈、測試或未知 | 原完整Windows19模組；新／刪除／改名模組或無已知測試也擴大。 |

每次真正產EXE仍必須：當前完整來源資格及治理Gate、實際原EXE21操作／重啟、5種引擎情境、人物／版本／無解及輸出保護、私人資料排除、上傳後實際下載完整程式ZIP並逐檔驗證。來源資格要求沒有放寬；產品bytes改變仍須取得新來源資格。Qt新程序隔離與180秒／EXE外部240秒硬期限保留，不以並行破壞隔離。新測試的平台範圍必須審查，Linux-only不得冒稱Windows PASS。

固定Windows底線含啟動、授權、下載、防誤打包、引擎路由、快取身分、隨包guard及安全報告。相關性未知不是空掃描通過。選中模組、原因、未知邊與基底／HEAD記在release-impact-plan.json。

## 授權、版本與啟動

普通dev/main/PR提交不打包。`release-speed-check/**`或人工dispatch只做診斷，不建立tag／Release。只有明確的`release-request/v<新版本>`分支可進入發佈，另須STATE.release_speed_optimization.release_request保存該版本、published=false與使用者本次發佈授權（scope=PUBLISH_WINDOWS_INTERNAL_BETA、user_request原文）。舊beta.2授權、既有tag／Release均不能拿來發新版本或覆寫。

產品版本唯一來源仍template_ai/__init__.py；新request只是待發授權，必須吻合該版本。STATE.windows_release保存最後實際發佈結果。舊pending_release及exe_policy保留beta.2歷史／舊治理相容，不改寫成新版本授權。每版仍須保存來源、相容／恢復限制、結果及GitHub精確讀回。

新發版時，Codex先按實際授權寫入上述新request與版號、取得新來源資格，再推對應request分支；沒有人授權新版本時不可填造授權。本輪request為null，只有診斷分支被觸發。新Release會保留完整程式ZIP、manifest、SHA與SOURCE_DOWNLOADS.json；原來源ZIP從公開舊版精確連結，下載校驗會完整再驗該來源內容並標示重用，不冒稱每次重新下載來源ZIP。

## 計時與驗證

release-timings.json記準備、離線安裝、影響計畫、工具測試、來源治理、Windows回歸、乾淨建置、真EXE、打包及下載驗證的真實秒數、結果；cache-transfer-timings.json另記Actions restore/save成本。cache-inputs記每物件命中、驗證、下載量，不把cache存取時間排除後宣稱全程加速。

本輪冷快取跑相同產品來源、27 wheel／11837元件／125來源檢查、原Windows199、EXE21／引擎5，再用本地HTTP實際傳輸程式ZIP及原下載驗證器。這是未發佈成品的loopback驗證，**不是GitHub公開下載**。未來實際發佈仍草稿及公開後兩次真GitHub下載檢查。另一乾淨runner只做真遠端cache hit與完整輸入再驗，不重跑相同無改動產品測試；明標不是第二次EXE驗收。

測得的cache準備節省不能當端到端修正交付的固定分鐘承諾。失敗、cache存儲未知／被跳過、外部私人作品／使用者硬體／實印資格均分開記錄。證據永久保存release-speed-evidence/v1及開發checkpoint，不能只依賴會到期artifact；大binary不放Git。

下次可說：「以目前已發佈版本為基準修正〔問題〕，依修正版加速規則先重現與選影響範圍，驗證快取後建置；完成必要EXE操作與真正下載校驗，再以新版本發佈，保存checkpoint，不新增費用。」
