# 當前精簡接手

- 核心零例行問答、按需rg/小段讀、一般輸出≤1600tokens；每可恢復階段及10分鐘GitHub checkpoint/逐檔readback/receipt。無多代理、EXE、main merge，提交[skip ci]。
- /workspace/template-Ai，dev/v0.1-first-version／PR2；active_contract FIXED70_REMAINING28_CONTRACT。原前輪28與本輪剩餘28分開。
- 本輪剩餘28已完成UI046/UI047/UI049/UI050/UI051五題，共52原條款；749/749正式PASS、0skip/0Qt錯誤、capture0、source unchanged。全75：49 VERIFIED／23 PARTIAL／3 DEFERRED；固定70：47閉合／23仍部分。CORE87／GOV7另計。
- 最新 docs/evidence/runs/RUN-REMAINING28-RUNTIME-003/run.json source 8f8f638a1096f0aeb8aebe2231d6d49b96970c05；143要求/claims合約digest吻合，原28已註冊5父題52全文條款；其餘23未完成，goal_complete=False。
- UI051：同SQLite FIFO seq、scope/session/CAS/共享WORKER、max200/paged50；psutil host/cgroup/RAM/CPU/IO/disk + Qt lag/foreground/hysteresis；48paged startup/server global search/lazy font，不eager all models/originals/jobs；壞policy仍可開GUI診斷，raw/正常DB close停timer/probe。
- 既有JOB/AUTO引擎移stdlib subprocess，bounded metadata，120s無邊界/取消10s才停子樹；SQLite item BEGIN不是DONE，真kill rollback、唯一active項FAILED後其他READY沿已確認scope繼續，retry_failed一次消耗/FAILED零auto retry。
- source登錄/owner與job.source_id同transaction；queue receipt故障FailClosed，明確恢復讀回原job/owner/scope/終態補收據、不重分析。源碼細節UI051_TIMEOUT_RECOVERY，原失敗/修正target logs全保留。
- read-only QProcess ledger查 source pages/作品紀錄/indexed+preflight另計，每頁50/4MiB/30s；實際SHA/stat/pins/cache核實，analysis與人審/排除/客戶歸屬分開。全庫有效已審數與原稿作品覆蓋未核實時明示未知，UI052另做真正batch closure。
- UI04611/UI04710/UI04911/UI05012原條重驗；WATCH001曾687PASS但1Qt closedDB整runFAIL不可改，002修正692PASS保留。本run不宣稱原生真AI全面、Windows/16GB RTX5050/VivoBook性能、真個資生產、獨立覆核或印刷通過。
- 37文字metadata保存GitHub；112媒體在.checkpoints/formal-media/RUN-REMAINING28-RUNTIME-003，FULL70_PUBLICATION精確source/sha/bytes；不宣稱strict全附件上傳。
- 下一UI052：現有quality_coverage是查詢/facets/unknown；缺exact批次邊界/分層分母/正式規則驗證/高風險個別處置/漏審阻擋/結案快照與變更重開/500+分頁。先保存原10條計畫與參照再開發，別把UI051 ledger或進度百分比當結案。
- UI031/032/REV02合法真AI/Windows字型版本與安裝、REV04實機仍未全驗；UI048 LAST、UI056D/REV03延後。新source變更前把143已完成標pending，保留previous evidence/清latest，再新source全量回歸。

- UI052原10逐條計畫已保存UI052_EXECUTION_PLAN；GE0.18.21 checkpoint及MicrosoftVSCode1.105.1 working-copy participants實際source/sha在REMAINING28_ENGINEERING_BASIS，重用既有SQLite/rules/facts/ledger，不安裝GE或商用服務。下步先143完成pending/previous證據、default collector加.jsonl，再同DB batch/member/schema。
- UI051 publication-scope真PASS在CP-20261015-REMAINING28-UI051-JOURNAL-PUBLICATION，原collector未含JSONL先用docs/dev/prepare_checkpoint_with_jsonl.py資料adapter補真正manifest/ZIP/ACK，未改舊run或waive文字；80aa1ca source followup已讀回。

### UI052 exact-boundary P1 WIP
- 已新增同SQLite COVERAGE_BATCH/MEMBER固定已登錄來源頁範圍、原路徑分組/同內容不同檔名獨立分母、來源/作品版本釘選、CAS與有界分頁；位元驗證明示不等於人審或結案。僅py_compile通過，尚未功能測試，不宣稱P1或父題完成。
- default collector已加入.jsonl；source改變，143歷史完成claims皆pending保留原證據，下一寫P1實際檔案/競爭/500+分頁測試，再做分層證據與規則/處置/結案GUI。整體仍5/28里程碑，23未閉合。

### UI052 layered review/closure backend WIP, 22 targeted PASS
- coverage_evidence/review/closure引用既有FACTS/RULE/SEMANTIC_ACTIVE/實際客戶關聯/模板版本；全來源切分需全頁且明列真實作品，7層個別人工審核，低風險僅既有核准noise-rule annotation。無來源／未解析不能藉排除隱藏；排除不算學習/版型通過。
- 結案實際hash在transaction前、鎖內stat+metadata/CAS重核；同transaction保存不可變receipt與batch link。source/model/review變更失效，明確reopen新batch保留舊receipt。22目標測試PASS含600分頁、diskfull整批回滾、漏層/缺頁/變更/reopen/missingreceipt。第一輪錯import analyser constant 4 errors原log保留，改正import後通過。
- 原10尚未完整：未登錄來源／目錄新檔分母、受控GUI/worker/capture、完整正式回歸待做。仍5/28里程碑，143 current claims pending，UI052父題未關閉。

### UI052 explicit files/root + lazy GUI WIP
- coverage_scope重用discover_sources visitor，明列檔案含未登錄/不存在，根目錄雙次有界遍歷/目錄stat釘選，partial/errors保留未知且禁止結案；新檔/改名使舊收據失效。無訓練自動dispatch。
- coverage_command重用runtime_worker.stop_tree隔離程序，命令/結果各32MiB、120s/cancel，GUI經既有run_job資源gate，結果未讀回不宣稱成功。新quality tab延遲載入，每批次/成員50，個別source切分、7層審核、排除、結案/reopen皆確切預覽+本次明確同意。
- 30 backend +4 actual Qt/subprocess +7既有quality =41 PASS。首GUI單module原import TestCase造成另執行30 backend，明列4GUI+30，已改module fixture防正式重複計數。
- 未完成：資源等待取消/重啟/大量新頁實測與實際capture、完整原10註冊及新source正式全回歸。整體仍5/28，143 claims pending。
