# 當前精簡交接

## beta.2隨包Inkscape：來源完成，繼續最終發佈

使用者2026-10-22明確採用隨包方案並授權完善代碼、打包EXE與Release；另要求局部變更影響除錯方案。dev/v0.1-first-version／PR2，不合併main、不覆寫beta.1 tag。程序版本0.2.0-beta.2；pending_release為本輪，windows_release仍保留已公開beta.1事實，未發佈beta.2。

**最後程式bytes固定**a91dc380；同code/test/fixture/tool manifest `f1a2cf7a817e7e3d0dca43ff93458f52d1526638aa816e7d223204f6abdf2908`。正式RUN-BUNDLED-INKSCAPE-BETA2-004來源42eb60fa（獨立Git讀回CP-20261022-BETA2-REVALIDATED-SOURCE-004）已由既有adopt_verified_execution與治理驗證：1986實際具名PASS（原1963保留＋23新）、262選定健康模組、27原版未插樁GUI、0合格執行runtime。原5外部資格仍NOT_VERIFIED／整體goal FAIL，不升172／166scope／75父題／AI8包50完成狀態。REQUIREMENTS與最新證據已連004。

**不是單次新全跑**：001因舊稽核測試短碼0200撞到合法SHA而停止，已改完整欄位／精確原payload digest驗證；002因新增renderer_identity內層錯型別會AttributeError而停止，已補null／數字／陣列／字串重建測試。003因暫存空間峰值不足有46 ENOSPC errors、2 class-setup error chains及1font-candidate deadline；原1945記錄與3runtime保留。相同code bytes的14整模組139案已單程序PASS，來源/斷言/180s限制不變；既有正式adopter逐案核對兩次來源與原始record，004採錄1986唯一案例，不灌重複數。證據在releases/v0.2.0-beta.2/linux-qualified-001、linux-environment-retry-001與formal004/module-inputs。

**下一步不可停在本機**：準備包含formal004全部附件＋本輪變更的新主CP，隔離還原→commit/push→verify_git_readback --ack，通過require-evidence／publication-scope。主CP已是CP-20261022-BETA2-SOURCE-QUALIFIED-001，snapshot1548c940，673項REMOTE_VERIFIED，嚴格require-evidence／publication-scope已PASS；禁止ack窄輔助CP覆蓋主正式指標。接著無diagnostic marker的候選HEAD推到精確release-request/v0.2.0-beta.2，跑最終Windows199選定案例＋原EXE21與5引擎情境＋125來源附件＋Release草稿／公開兩次全下載逐檔hash。只有真發佈／讀回才改published。

Windows probe002/66d9/run39777630190已實際PASS原14＋7、無系統兩phase＋有系統控制（各8實際呼叫都在bundle）、缺exe／壞dll兩情境與真support CLI及點陣獨立；它是診斷，不能取代最後EXE。probe001在測試機rename安裝目錄遭拒，改官方choco卸載／重裝並檢查原目錄不存在，產品路由沒有改備援。

官方完整11592檔Inkscape1.4.2 ebf0e94已鎖定，125對應來源物件共866.2MiB已查證，完整二進位GPL3-or-later並保留相依授權。最新額外data step從精確IDW88保留原授權bytes，待定向license-stage及最終Windows驗證。早期8f／42eb缺stage結果，不算PASS；查到稽核輸出目錄串接錯誤，68c7207已改共用OUT，run39789443841定向封裝PASS：11837files／242原授權檔，license-stage-002已原生Git精確讀回。第一輪diagnostic本體11594files，最終加入授權後的檔案數以實際結果為準。

局部除錯方案CHANGE_IMPACT_DEBUGGING.md／RESEARCH.json完成，參照Microsoft TIA、coverage contexts、testmon、Cosmic Ray；靜態反向圖＋動態覆蓋＋設定／資料／外部工具契約保守聯集，直接／流程／發佈三層。自動選測器尚未實作。兩個路由mutants均被抓。相同工具實掃beta.1來源與最後app：0新增／3453既有／1resolved，static-delta-002；初始基準未刷新。既有靜態項仍待判讀，不能稱全無錯誤。

49份舊輔助native tree JSON可逆gzip逐份roundtrip SHA一致，回收604.1MiB（加先前8份共約723MiB），maintenance/READBACK_METADATA_COMPRESSION_20261022.json有還原命令；沒有動正式證據、checkpoint ZIP、目前主CP或active source proof。最近約900MiB可用，大型Windows包／來源archive只在標準公開runner處理，雲端只取小報告。無新收費服務／API／試用／子代理，私人作品／字型／DB／模型留本地。原真實作品、使用者Windows效能、實印、新手、完整OS斷網資格不冒稱通過。

最終native001/a45/run39792844827在checkout前置失敗，Windows Git長路徑未啟用，新的capture/cache路徑過260；沒打包／沒tag，未有native分支RUNNING記錄，公開job annotation已保存windows-native-001。兩個Windows工作流程checkout前加core.longpaths true（保留autocrlf false）；純建置環境修正，program digestf1a2與1986／27證據仍有效。下一推新候選再跑最終native，不重跑Linux全套。

最終native002已確實RUNNING：fd1a3f9ea826297d696217db5c54353733412bb5／run39795277849，長路徑checkout已通過；local observer session3183將精確收取到releases/v0.2.0-beta.2/windows-native-002。不要重推release-request或改code；原source digestf1a2與全附件673主CP有效。若沒有起始evidence記錄，先查公開job annotations，不能把舊66d狀態當新run。後續需真公開下載、不可變tag、final完整CP＋Git精確讀回。

最終native002/fd1/run39795277849：Windows199實跑198PASS／1FAIL／0runtime，沒打包。唯一失敗是新DLL完整性測試先比較路徑時Windows TMP的RUNNER~1與resolve後runneradmin字串不同；另priority測試已resolve預期而PASS。沒有錯選外部engine。改CI TMP/TEMP為RUNNER_TEMP內經Path.resolve的短路徑，保留所有原測試方法／斷言／180s與產品碼；下一重跑Windows199，Linux1986／GUI27同code f1a2有效。原完整原生報告windows-native-002保留。

目前最終native003：ee5f6cdb3178e9c99873a05a0fd3450365897a37／run39799674358已RUNNING，observer session69966→windows-native-003。Canonical TEMP在CI內由Path.resolve產生，原測試／產品bytes皆不變。等真結果／全下載，不能先標已發布。MAINTENANCE_NOTES列已確認工具class-setup記錄待辦及外部資格限制。
