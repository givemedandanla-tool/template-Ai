# 雲端重建草稿（尚未發布）

本輪僅保存 install_script／start_skill 草稿，未發布或啟動新資源。既有 repository ref、網路、密鑰需求與執行環境需求均保留。工具原碼尚未推送；若未來環境沒有本輪檔案，會明示 LOCAL_ONLY，必須先還原使用者保存的交付包，不能假稱遠端已可重建。平台草稿不是程式碼遠端備份。

## 追加的安裝段落

```bash
# DEV-QUALITY-001: free local tools only; absent unpublished sources are explicit.
if [[ -f docs/dev/debug_tooling/bootstrap.py ]]; then
  .venv/bin/python docs/dev/debug_tooling/bootstrap.py
  .venv/bin/python docs/dev/debug_tooling/bootstrap.py --check
else
  printf '%s\n' 'DEV-QUALITY-001 is LOCAL_ONLY: restore the user-provided verified patch/bundle before using quality tools.'
fi
```

## 追加的接手說明

DEV-QUALITY-001：使用者要求零新增費用、單一 Codex，不啟用子代理／外部模型／新 runner 或收費功能。按需讀 docs/dev/debug_tooling/README.md、WORK_PACKAGE.json、BACKLOG.json；有檔案時用現有應用 Python 執行 bootstrap.py --check。只有明確準備工具時才執行 bootstrap.py；一般 quality.py check 絕不下載或安裝。保留既有基準與告警，檢查全部應用檔案以涵蓋新對舊重複；不因數字而自動重構。
本輪工具原碼與提交因無法核實遠端觸發費用而僅在本機，repository ref 維持原已驗證遠端。若新環境沒有 debug_tooling，先使用使用者保存的 DEV-QUALITY-001 本機交付 ZIP 依其基底核對／還原，標 LOCAL_ONLY_NOT_AVAILABLE，不虛構遠端來源或宣稱工具已就緒。新 skill 的檔案／顯式使用與平台原生辨識分開報告。當前雲端實測 Python3.12.14／PySide6 6.8.3；3.11為最低語法目標，Windows/native3.11尚未驗證。所有遠端寫入前須有零新增費用的充分證據，否則保存本機提交／checkpoint／patch，不改 CI、保護、帳務或既有 network/proxy/CA。
