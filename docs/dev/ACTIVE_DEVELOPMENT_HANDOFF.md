# 當前精簡交接

## 目前任務：beta.2隨包Inkscape＋變更影響除錯方案

2026-10-22使用者明確採用隨包方案、授權完善代碼及依規則發佈Release；另要求研究合理局部除錯範圍。目標v0.2.0-beta.2，plan在releases/v0.2.0-beta.2-plan.md。既有beta.1與tag8b95不覆寫，不合併main，不啟用新付費服務／API／試用／子代理。私人作品／字型／DB／模型留本機。

新增inkscape_runtime.py：frozen只選app旁engines/inkscape、版本1.4.2、manifest＋release-info pin及完整檔案驗證，不看env/PATH/系統；source模式保留外部工具。原wrong-route／missing-bundle兩個紅燈已實際重現，11路由／完整性及安全報告測試及5快取測試PASS（非真EXE）。importer向量快取加入工具身分／新路徑，保留舊cache_matches完整性／原資料，不因工具更新覆寫舊cache；點陣輸入不依賴工具。

Windows分佈audit run39769146036/eecb來源已讀回research-evidence/inkscape-1.4.2-beta2（commit945469）：官方Inkscape1.4.2 ebf0e94，11592files/583742481bytes，exeSHA08eca529…e0e64。完整二進位依上游COPYING為GPL3-or-later（多數原始碼GPL2-or-later）；不能只引用Chocolatey的GPL2簡表。第二輪run39772431663／research證據51381d5已完成：118 runtime套件，115精確來源archive可取得（772.2MiB），2舊壓縮格式尚查；GraphicsMagick由官方腳本另編1.3.43，正在短程[source-gap-check]。已讀官方IDW88（GitLabproject46863172，524800330bytes，SHAfefbd2…e5bac）套件db／授權／精確來源取得；不要把來源義務當已完成。

下步：完善包內散佈鎖定／授權來源附件、路由／快取邊界與安全報告、加真正EXE無系統工具及外部誘餌測試，依既有流程新正式來源資格與Windows驗證／公開全下載。工具真正存在與被實際呼叫須分開證明；不以mock／source-mode代替原生EXE。原172要求／166scoped／75父題與AI8包50外部資格不自動升級。

除錯研究已讀coverage.py contexts、pytest-testmon、Microsoft TIA與Cosmic Ray公開資料（快照.cache/beta2-research/references）。設計反向相依圖＋動態覆蓋＋設定／外部工具契約保守聯集、固定安全底線、未知時擴大、測試選中／排除理由；使用原wrong-route紅燈與故障注入檢驗檢查力度。保留Qt程序隔離與最後發佈Gate，日常不每改一次全跑。尚未冒稱新選測工具已完成。

## 已發佈基線與保存

beta.1已公開、原176Windows＋真EXE21＋1220下載hash PASS；證據releases/v0.2.0-beta.1/windows-native-007-published。主CP仍CP-20261021-WINDOWS-BETA-PUBLISHED-001，449項REMOTE_VERIFIED／369正式附件，基底4734990a。它是舊版已驗證基線，不代表本輪新程式已資格化；不要以小型讀回覆蓋主正式指標。新code後需新正式證據，舊失敗／取消保留。

空間緊，8個舊輔助tree.json已可逆gzip，內容hash全部一致，回收118.86MiB；maintenance/READBACK_METADATA_COMPRESSION_20261022.json含逐份還原命令。不動checkpoint ZIP／正式證據／私人資料；目前約527MiB可用，Windows大檔在標準runner處理，雲端只取小報告。原api.github.com不通但原生Git與GitLab／rawGitHub可用，無需新API key。

本輪真實抓到安全報告回歸：新增工具資訊間接載入numpy，破壞原無site-packages CLI。保留support-regression-red-001；converter_version已搬到標準庫runtime，原21安全報告及11路由測試PASS，targeted-support-green-001記錄。尚非發佈資格。

打包程式WIP：bundled_inkscape_build.py＋125份來源lock；prepare完整官方11592檔比對→manifest pin→PyInstaller→install→原EXE21＋無系統／誘餌／缺檔損壞／有系統控制→來源附件→精確vendor清單→Release。first-version.yml已轉精確beta2分支，治理授權擴充保留原beta1四測試。新guard4測試與原6相關模組PASS，真正Windows尚未執行，published仍false。除錯方案CHANGE_IMPACT_DEBUGGING.md已寫，故障注入002正確2 PASS、兩個mutant皆被抓（非原生證明）。

Windows probe002/66d9/run39777630190真EXE PASS：原14＋7、無系統兩phase＋有系統控制（各8實際呼叫全包內）、缺exe／壞dll兩情境與真support CLI。probe001是測試機目錄rename被Windows拒絕；改正式choco卸載／重裝且校對目錄不存在，未改產品路由。補充原IDW授權檔按原bytes封裝的新data step尚待最終Windows執行。
正式001因原test_customer_identity短字串0200碰到合法SHA而停止，原FAIL保留；test改為完整允許欄位、原payload精確digest／id／state／actor／reason核對（非弱化隱私），12原測試target PASS；下一重新跑1985完整正式002。產品演算法未因此改。static same-tool vbeta1實際來源對照0new／3453existing／1resolved，未刷新基準。

正式002已於12:33UTC啟動：source22198c8b3999775065c792903cf6eb7fc4b1dc30，2個原生獨立Qt worker，1985cases；live路徑.checkpoints/formal-live/RUN-BUNDLED-INKSCAPE-BETA2-002，log.cache/beta2-formal-002.log。未完成前不改code_only來源、不重啟同ID。完成後可執行已加guard的releases/adopt_beta2_qualification.py；需再準備包含全部正式附件的新主CP並ack，不能拿輔助CP取代。最終Windows需納入新dependency license data step，再發佈；beta2尚未公開。

正式002已停止（不是PASS）：進一步局部壞cache重現renderer_identity=null造成AttributeError，紅燈linux-interrupted-002。importer新增內層dict guard，null／數字／陣列／字串四型別安全重建；6cache-identity及6原source-cache PASS。下一固定這個source後正式003共1986。cgroup實際4CPU／32GiB，採3個既有隔離worker，保留180s／原斷言／Qt獨立程序；不啟用代理。不得接續001／002為正式成功，也不再改code_only來源。adopt helper已更新003與1986 guard。
