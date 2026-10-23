# Qt 接線整合 agent 任務

先讀 AGENTS、目前契約與 template-ai-qt-interaction-review skill。重用真實 MainWindow、
DesignSession、InputGraph 及 bridge；整理畫面時不能另建一套排版／資料引擎。
保留既有入口與專業工具；拖動和位置選單使用同一相對意圖核心。
核對資料更正、取消、復原／重做、候選、確認及輸出的資料與版本；保護晚到 worker 回呼。
不得恢復客戶字級／字寬／單雙排控制，不默默更換既有模板或定稿。
只修改主代理指定擁有檔案；不改共享治理檔、不 git commit/push、不派下層代理。
以真實視窗＋合成資料測試，報告修改、實際測試、限制與下一個可恢復點。
