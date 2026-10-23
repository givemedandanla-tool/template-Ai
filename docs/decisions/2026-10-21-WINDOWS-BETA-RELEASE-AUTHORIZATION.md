# Windows內部測試版明確發佈授權

使用者要求：「好，現在我要你在github發佈程式本體exe，讓我投入實機測試」。依已採用RELEASE_MAINTENANCE_POLICY，授權本次v0.2.0-beta.1 Windows x64原生建置、驗證、Pre-release發佈、上傳及下載讀回；取代舊EXE延後，但不合併main、不部署、不新增付費服務。

為使用已授權且可用的原生Git介面啟動本次既有GitHub標準Windows runner，first-version.yml只接受人工dispatch或精確release-request/v0.2.0-beta.1分支。一般dev/main/PR仍不打包；版本專屬請求分支的每次推送必須是本次修正後候選來源，不是日常CI。來源／實際EXE兩階段驗證必須通過才建立不可變tag與Release。證據分支release-evidence/v0.2.0-beta.1保存來源、工作流程網址、狀態與下載校驗，需實際Git讀回。

本機api.github.com被平台政策阻擋；已保存加入API／附件主機的網路草稿，但尚未生效。Git讀寫不等於Actions已啟動；截至此WIP僅確認請求分支已保存，未取得Windows回執，不能宣稱EXE已建置或發佈。

教學／外部知識庫草案維持待核對。真實作品／使用者Windows硬體效能／實印／新手完整資格維持原界線；不以beta或工具掃描替代正式輸出Gate。私人資料與字型不進成品，手動安全報告維持本機。
