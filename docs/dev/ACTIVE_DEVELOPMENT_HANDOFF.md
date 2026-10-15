# 零例行對話、持久化接續入口

使用者要求：依規劃自主推進，參照數學、成熟開源及商用方案思路；每階段checkpoint保存GitHub；新對話可直接接續，不重問是否繼續或保存。

目前UI043、045、020～027共10原父題的軟體條款SELF_VERIFIED：87條驗收、498/498測試PASS、實際Qt與三格式數位檔。固定70累計14完整／56剩餘；原75為16完整／56部分／3延後，CORE87／GOV7分開。來源、證據、收據及未驗證外部條件見STATE。不宣稱全產品完成、實體印刷／Windows／私人AI全面保真或獨立覆核。

恢復順序：AGENTS→STATE→本檔→最新HANDOFF段→STATE.active_contract及REQUIREMENTS→最新WORK_LOG／收據。開發在dev/v0.1-first-version／PR2，main是較早文件狀態。舊/local完整聊天無法取得，已找回的GitHub決策與版本是可核對依據。

下一項UI003自動管線，接UI004/005/007/008，詳見NEXT_AFTER_TEN_PARENTS。先寫原條款、具名驗收及BEGIN checkpoint，再改碼。真正缺外部條件只阻塞相依驗證，先做其他已授權工作。

環境：.venv/bin/python；重建bash tools/cloud_setup.sh；測試使用XDG_CACHE_HOME=/workspace/.cache、QT_QPA_PLATFORM=offscreen。雲端設定與大型檔案按區域讀取策略見CLOUD_ENVIRONMENT_SETUP；不把整倉庫或base64附件塞入對話。

每10分鐘及可恢復階段prepare→commit/push→fresh fetch→commit/tree/blob讀回；收據下一提交保存。本機ZIP不能冒稱GitHub保存。新證明媒體依既定metadata-first留本機與精確hash，程式／tests／text全保存，不宣稱全附件公開Gate。保留未提交、ignored與local-only提交，不reset或force checkout。

不啟動多代理、不合併main、不建EXE；[skip ci]避免Actions自動啟動。不需要付費API或新token。零對話表示免例行問答，必要狀態仍依較高指令回報；沒有啟動agent時不會全天候背景執行。
