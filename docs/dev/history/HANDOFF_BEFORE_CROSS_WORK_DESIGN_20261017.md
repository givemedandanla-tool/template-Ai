# template-Ai 接續入口

目前28父題：25題完成自我驗證、3題待外部證據；325條原驗收320通過、5未驗證。所有可獨立完成的軟體工作已實作並以CURRENT008驗證；不可宣稱28全完成。

先執行`python tools/resume_status.py`，依序讀 [STATE](STATE.json)、[精簡當前交接](ACTIVE_DEVELOPMENT_HANDOFF.md)、[外部驗證條件](REMAINING28_EXTERNAL_QUALIFICATION.json)。目前來源提交38700310960ad7c77a5f82a71a8798e03f5ae508；[正式軟體證據](../evidence/runs/RUN-REMAINING28-CURRENT-008/run.json)為1549測試全通過／capture0／runtime0／source unchanged。整體run仍FAIL，因Windows字型實測、真實Illustrator來源訓練、指定Windows硬體實測缺證據。

分支dev/v0.1-first-version／PR2，未合併main；不開EXE、agent或付費服務。零例行對話、按需讀檔、GitHub checkpoint/逐檔讀回規則見AGENTS及CONTEXT_AND_PERSISTENCE_RULES。舊長版交接保留docs/dev/history/HANDOFF_BEFORE_CURRENT008_SCOPE_CLOSURE_20261017.md；不需重貼原聊天。
