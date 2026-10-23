# Qt 字型生命週期的單程序混合測試診斷

這是額外合成診斷，不是新的完整回歸，也不是 Windows 字型資格。
來源 HEAD 為 `1d65dbe`；診斷沒有修改 source、test、tool 或 registry。
原測試自身只建立及清理其合成本機資料。暫存 runner 僅在原斷言失敗後讀取狀態；沒有改斷言、重寫結果或關閉 Gate。

## 兩次實際測試組合

`<TMP>` 代表診斷用暫存目錄。原始私有路徑不納入此公開說明。
每次都有180秒外層上限，沒有第三次重跑。

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=tests .venv/bin/python <TMP>/diagnose_gui_parent.py test_desktop_workspace test_parent_navigation
QT_QPA_PLATFORM=offscreen PYTHONPATH=tests .venv/bin/python <TMP>/diagnose_gui_parent2.py test_desktop_workspace.DesktopProductionTests test_parent_navigation.ParentNavigationTests.test_real_qualified_and_blocked_candidate_sections_auto_choose_and_revalidate_current_input
```

第一組15項：14 PASS、1 FAIL、0 ERROR，81.826秒，實際退出碼1。
第二組7項：6 PASS、1 FAIL、0 ERROR，66.310秒，實際退出碼1。
兩組完整原ID及結果在隨附diagnostic.json；共同失敗仍是原`qualified_candidates.count()==1`斷言。
若只重現同一測試順序而不輸出診斷，可以將上述暫存runner改為`-m unittest`，其餘測試名稱保持不變；此替代命令未另外執行。

## 實際觀察

前景已COMPLETED，兩候選均存在、世代一致。好候選valid=True、issues=[]，因SNAPSHOT_FRESHNESS UNKNOWN進入待核對區；窄框候選仍因WIDTH正確硬性阻擋。

同一個沒有綁定font_asset的Noto Sans CJK TC要求：

- GUI實際取得Noto Sans CJK TC / Regular。
- 失敗後的全新診斷thread取得OpenAI Sans / Regular，其依賴摘要完全等於原背景worker儲存的摘要。
- GUI與背景等價thread的實際字面指紋及依賴摘要不同，精確hash保存在diagnostic.json。

因此不是候選未產生、世代改變、未等背景完成或新增縮放操作。已定位為前序多Library／Qt字型註冊生命週期後，不同thread實際字面解析不一致；正式輸出Gate依實際差異正確保守阻擋。
尚未把最初的Qt註冊／移除與暫存字型路徑清理序列最小化到單步根因，也不宣稱一般單工作台或Windows全部字型情境均已驗證。

## 維持的範圍

不修改Gate、不更改資產未綁定的混合多Library字型環境來湊PASS。實際字型／設備資格依使用者決定保留後續本機驗收。
正式fresh-module target006的15/15 PASS是另一份證據；保留本次兩組反例，不相互覆寫、不累加為新的唯一功能測試數。
公開附件只提供本JSON與說明，不附完整字型清單、字型bytes、原始來源或敏感絕對路徑。原始暫存診斷log含較多環境資訊，勿原樣當公開附件。
