# 第三方測試資料的打包修正

原始證據：windows-native-006-payload-failed。04418ac0／run39632714813 的176／176 Windows來源案例、16模組49新Qt程序、0runtime，以及真EXE原14＋7兩階段檢查都PASS；原包內容Gate拒絕 `_internal/sklearn/datasets/tests/data/openml/id_1/api-v1-jd-1.json.gz`，因此沒有tag或Release。失敗完整保留，不把操作驗證通過寫成發佈成功。

釘定官方pyinstaller-hooks-contrib v2026.9的hook-sklearn.py明確執行`datas = collect_data_files('sklearn')`，也收進套件自己的測試資料。官方來源與SHA見payload-filter-controls-001.json。

修正限於docs中的建置配置：Analysis後、PYZ／EXE／COLLECT及實際EXE驗證之前，移除sklearn／numpy／scipy三個已知第三方根目錄下tests路徑的資料。保留執行資料、授權、原始產品、人物歸屬、快取／輸出及最終包內容Gate；不允許以此機制隱藏產品tests、私人DB或字型。零命中與未知TOC形狀拒絕建置。每次記錄政策hash及精確移除清單。

隔離控制7項PASS，包含Windows分隔符、保留runtime／license／私人候選、零命中拒絕、未知形狀拒絕、真實產生spec讀取及mock執行順序、UTF8選項和重複配置拒絕。這是配置示範，不是真實Windows EXE驗證。新正常候選仍須完整原176與過濾後真EXE21檢查、原打包Gate及兩次完整下載校驗，不複製舊來源提交的PASS來代替。

使用者另詢問Inkscape：啟動與既有模板製作不強制依賴；PDF相容.ai／PDF、SVG及圖片已有Qt備援，讀取不代表語意／資格完整。快速開始已補正，此輪未更改匯入程式或要求使用者新付費服務。

## 預先發現並修正的新目錄契約問題

最初7個配置控制漏掉原exercise要求output.mkdir(exist_ok=False)。初版filter把報告寫在package-check內，會預建輸出目錄；這是新增docs配置的接線缺陷。尚未跑到該步的f203／run39636966203不視為通過，明確替換其發佈前流程。新配置把建置報告寫在artifacts根，原EXE驗證成功後才複製到證據目錄，原exercise不修改。第二版9控制PASS，包含真檔案系統重現舊錯誤與新目錄契約；Linux原兩階段21來源檢查PASS，明確非WindowsEXE資格。工作流程僅在帶[supersede-prepackage-run]的明確新請求時取消已確認發佈前舊run，日常仍序列且不打包。新候選仍完整重跑原176、真EXE、原inventory及下載校驗。
