# 當前精簡交接

修正版發佈加速已完成，詳[交付](releases/RELEASE_SPEED_DELIVERY.md)、[政策](releases/RELEASE_SPEED_POLICY.md)與STATE.release_speed_optimization。dev/v0.1-first-version／PR2，不合併main。最後產品版仍v0.2.0-beta.2／來源af97b108；本輪沒有新tag或Release，舊版公開manifest／SHA與tag已精確讀回未變。

4項工具能力：27固定wheel離線hash安裝；精確引擎／125來源ZIP重用再驗；保守AST影響選測（base∪head、動態契約hash、核心／未知完整、固定8底線、報告資料不誤擴大）；逐階段真計時。長期builder ref release-speed-check/20261023-001用於跨版本cache，普通dev/main/PR不建置。新發版需STATE新request授權＋提交標記＋版本request參照同HEAD；目前release_request=null，不自動推builder重建／發布。

原生native002來源7e8cf994／run39894882425：199／199 PASS、0runtime，原真正EXE14＋7／5引擎情境全PASS，24次包內呼叫；未發布包的loopback HTTP傳輸與原verifier13060檔PASS。另一乾淨runner warm001確實Actions hit／29物件完整重驗，沒有第二次EXE宣稱。最新發布guard／metadata分類／batch索引另由bb431f68／run39897343317實跑Windows42／0skip＋真project索引；critical validation path／輸入pin／選中19模組與native002一致，final-validation-composition.json證明分開驗證，不冒稱一次新全跑。

實測：冷準備含miss61.11秒，遠端熱含還原37.27秒（還原14.47、驗22.80），同機熱10.77；cache首次save12.22另記，Actions傳輸byte未量測不能稱0下載。Git索引34.53→5.17秒。單次標準runner觀察，不能與過去公開發版直接算全程加速。本輪未發布新產品；未來發布仍草稿及公開後兩次真GitHub下載＋所有程式檔hash，來源ZIP重用會明標且全125再驗。

native001/c6bfd14b初期59秒拒絕CRLF source map，原失敗保留；真發布map b8d3…/48199與Git LF bc027…/47178已重現。保留manifest／每檔SHA，另比較JSON語意；沒有改pin求過。輸入驗證通過即存cache，產品失敗不抹除，續接同source及INPUTS_VERIFIED後再驗。錯誤增加bounded message／traceback。cache公開用量原0，1.51GB輸入低於2GiB，既有≤8GiB才存、不改quota／帳務。無付費API／試用／runner／模型／子代理。

產品、既有tools／tests bytes仍f1a2cf7a817e7e3d0dca43ff93458f52d1526638aa816e7d223204f6abdf2908；原正式RUN-BUNDLED-INKSCAPE-BETA2-004保留1986唯一PASS、原1963＋新23、27原版GUI與所有失敗／同bytes139復驗（不是一次新全跑）。原5外部資格仍NOT_VERIFIED、goal FAIL，172／166scope／75父題與AI8包50資格未升級。主CP仍須含正式004全部369附件，禁止窄metadata ack覆蓋；看STATE最後收據。舊輔助tree JSON可逆壓縮清單與未出貨工具class-setup次級KeyError見原maintenance紀錄，未刪私人資料或原checkpoint ZIP。

下一步等使用者本機beta2實測／明確修正與發版要求，回版本、步驟、預期／實際及手動安全ZIP即可。私人作品／字型／DB／模型留本地。Illustrator、網頁手機、教學草案及原真實作品／硬體／印刷／新手／完整OS斷網資格不在本輪升級；coverage context動態索引也尚未導入。不自行再跑全庫或建立新版本。
