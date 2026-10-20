"""Finalize only after all current-source local gates; keep formal remote gate blocked."""
from pathlib import Path
from datetime import datetime,UTC
import collections,hashlib,json,subprocess
F=Path(__file__).resolve().parent;ROOT=F.parents[2]
def load(p):return json.loads(p.read_text())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
full=load(F/'full-regression-final-010/summary.json');assert full['software_execution']=='PASS' and full['planned']==1921 and full['runtime_errors']==0 and full['original_test_ids_preserved']
stock=load(F/'gui-stock-captures-final-003/summary.json');assert stock['status']=='PASS' and stock['passed']==27
native=load(F/'native-gui-final-006/native-runner-result.json');assert native['status']=='PASS' and native['source_unchanged'];native_cases=sum(len(r['test_ids']) for r in native['jobs']);assert native_cases==19
ledger=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];counts=dict(collections.Counter(r['status'] for r in ledger));assert counts.get('UNREVIEWED',0)==0 and sum(counts.values())==11798
latest=load(F/'release-diagnostic-comparison.json');assert latest['unreviewed']==0 and latest.get('final_binding');clones=load(F/'final-clone-review-ledger.json');assert clones['all_candidates_reviewed'];clone_count=len(clones['reviews']);new_count=sum(r['status']!='ORIGINAL_REVIEW_LINKED' for r in latest['findings']);union_count=len(latest['findings'])
integrity=load(F/'ledger-integrity-final.json');assert integrity['status']=='PASS';gap=load(F/'unlinked-clause-dispositions.json');source=full['source_commit'];now=datetime.now(UTC).isoformat()
versions={};coverage={}
for scope in ['application','tools','tests']:
 report=load(F/f'final-release-{scope}-standard-003/report.json');versions[scope]=report['versions'];coverage[scope]=report['coverage']
rows='\n'.join(f'| {s} | {v["expected"]} | {v["cpython_compile"]} | {v["pyright_files_analyzed"]} |' for s,v in coverage.items())
report=f'''# 第一次下載前全面查證：本機範圍完成

狀態：**LOCAL_SCOPE_COMPLETE_WITH_REMOTE_GATE_BLOCKED**。最後程式來源 `{source}`；GitHub 基底 `0e7b8aee82331ff6efa02a1a8233ff85689b660a`，工作分支 `dev/v0.1-first-version`。本報告產生時間：{now}。

已完成本次可在既有環境驗證的全盤掃描、根因修正、回歸、實際介面及證據交接。這次沒有 EXE；本機還原包的精確提交以 `.cache/debug-tooling/audit-delivery-20261020/manifest.json` 為準。該目錄 receipt 或ZIP內RESTORE_RECEIPT標記 LOCAL_SAVED_AND_RESTORE_VERIFIED 才代表還原包已製作並驗證；包的雜湊在提交後產生，收據為準。

## 實際驗證結果

- 最後完整回歸：**1921 PASS、0 FAIL、0 ERROR、0 SKIP、{full['healthy_modules']}／{full['modules']} 健康獨立模組、0 執行期錯誤**。原1850項保留，新增71項有意義案例，執行期間來源未改。
- 原有27組 GUI 操作／擷取：27／27 PASS，原指令、原斷言、原時限、沒有觀察器包裝；實際桌面另19項 PASS、11張畫面。它們會重複部分單元案例，不相加冒稱不同測試數。
- 7項獨立數學標準答案與資料庫相關24項案例包含於正式目錄；涵蓋小規模窮舉最佳指派、預設優選／確定性、聯合區間拒絕，以及雙連線讀取、版本保護、巢狀／例外交易。
- 三範圍標準、實際執行環境型別及近似查重，共9份最後掃描完成。CLI完成不代表警告為零。
- 原11798筆診斷全部逐筆分類；原始指紋／出現次數完整保留，引用證據與修正提交均可讀。9187筆為型別／資料契約待改善，1856筆為工具或原生宣告限制，740筆與已修正共通根因相關，15筆屬原先外部驗證限制。這些筆數是提示，不是獨立產品故障數。
- 最後兩套型別設定合併{union_count}筆出現項，其中{new_count}筆新增／變體已另行判讀，0未審；原基準、忽略規則與掃描力度沒有為通過而刷新。
- 完全重複7組維持原數並已判讀；近似／結構候選{clone_count}組全判讀，4項低優先共用候選留待專案化重構。保留不同測試意圖和必要差異。

| 掃描範圍 | 應掃檔案 | CPython實編譯 | Pyright分析 |
| --- | ---: | ---: | ---: |
{rows}

3個 Ruff 解析限制已由 CPython及另一分析器接受的語法對照，保留原提示與限制；不是刪除產品程式換取通過。jscpd最低長度以下的檔案及第三方／產生檔排除理由留在有效設定和coverage。近似AST的測試檔排除限制另有明列。

## 已修正的10類問題

| 類別 | 結果 |
| --- | --- |
| 原生視窗 API 被資料欄位遮蔽 | 恢復 window、font、size、width等原生行為，相關欄位及呼叫者一併修正 |
| 重複關閉處理覆蓋清理 | 關閉前保留未保存／工作中保護，成功關閉才清理目錄連線 |
| 取消旗標遮蔽 QObject.event | 分開取消旗標，實際原生事件可正常送達 |
| 列表混用篩選前後版本 | 完整列解碼或有界SQLite讀取快照；涵蓋訓練、重大重審、Logo及5條目錄／審核列表。確認仍核對最新版本 |
| 舊／已關閉視窗回呼 | 過期工作不碰已關閉資料庫、不清除新工作的忙碌狀態 |
| 無必要的冷啟動重型載入 | 沒有可分析文字／備註時先返回，需要時才載入模型工具 |
| 確認期間切換資料／草稿 | 跨選檔、轉換、確認與寫入核對同一對象和內容；發布加版本CAS，拒絕套到另一份稿 |
| Type3 PDF字型未知值崩潰 | 回報來源字級／字型為UNKNOWN，保留證據，沒有編造原稿字級 |
| 重開已派送工作參數錯誤 | 找到精確原工作，正在跑另一工作時不切換、不重啟 |
| 草稿讀取失敗留下混合狀態 | 完整驗證新來源／作品／框位後才替換目前工作，失敗保留原狀態 |

測試與擷取程式也修正了欄位更名後漏接的尺寸、控制項與fixture。所有重現失敗、中斷與無效測試前置都保留，無效樣本未當成產品故障或驗證成功。讀取快照的包裝以ParamSpec保留公開型別；隔離錯型別樣本仍被Pyright拒絕。

## 入口、限制與仍待實機項目

10條輸入／版本／預覽／修正／輸出／恢復入口、40個來源錨點及訊號清單已更新來源雜湊並綁定本次結果。172需求、825條驗收的817條已有測試連結；8條無完整本機連結皆屬原PARTIAL／DEFERRED，逐條原因在 `unlinked-clause-dispositions.json`。連結及數量不代表測完全部可能分支。

原172需求的166明列範圍、3部分、3延後與原AI8包／50條真實資格維持不變；AI8包仍8部分／0完整真實資格。以下保持使用者原先延後安排：Windows字型與安裝權限、私人Illustrator／字型／真實學習品質、指定硬體效能、實體印刷、對外客戶存取防護及已延後產品範圍。Linux合成資料不代替這些資格。沒有向使用者索取私人作品。

核心仍保留人物／公司／共享歸屬、穩定ID、Logo綁定、固定／家族／定稿版本、無解拒絕、預設優選與相對位置規則；沒有增加客戶字級、字寬或單雙排控制。仍需改善的精確型別、缺少參照時更明確的領域錯誤及4項重構候選，保存於 `FOLLOW_UPS.json`。

## 工具、費用與保存

沿用固定版本Ruff、Pyright、jscpd、本機unittest／Qt隔離及diagnosing-bugs／dry-refactoring明確讀取入口；沒有託管分析或外部模型。工具及技能的來源、授權、版本與重建方式見 `../debug_tooling/README.md`。技能的檔案與顯式示範可用；目前平台原生自動識別仍屬先前未驗證項目，不能冒稱自動載入。

本輪沒有啟用新收費功能、試用、付費API／模型、runner、Codespaces或子代理，沒有修改帳務。未讀取整個帳戶帳單，不宣稱帳戶實際總扣款為零。

沒有推送、PR、CI、合併或部署。使用者的零新增費用規則優先；缺少可核實遠端觸發費用資訊，故保存在本機提交及可還原交付包。正式治理兩項檢查仍因既有證據來源過期而FAIL，新正式證據又需要真實遠端來源讀回；本輪沒有偽造GitHub收據、關閉Gate或把本機結果標REMOTE_VERIFIED。這項遠端資格與本機測試結果分開。

請保存還原ZIP；尚未推送的成果不能只依靠GitHub找回。ZIP包含相對已知base的binary patch、Git bundle、變更檔備份、manifest與白話還原說明；驗證會在隔離資料夾實際套用補丁，逐一比對所有變更內容／模式。私人作品、字型、DB、模型與.cache工作資料不打包。

## 下次直接貼的指令

「請接續 template-Ai，先核對還原包manifest的base／head，讀AGENTS、STATE和ACTIVE_DEVELOPMENT_HANDOFF，跑resume_status。使用既有除錯／查重環境分析我提供的安全報告，重現後做最小根因修正、相關回歸及checkpoint；保留原基準與外部資格，不開啟需額外付費的服務。」

專業證據：`full-regression-final-010`、`gui-stock-captures-final-003`、`native-gui-final-006`、`selected-stock-gui`、`ledger-integrity-final.json`、`release-diagnostic-comparison.json`、`exact-clone-final-review.json`、`final-clone-review-ledger.json`、`entry-path-audit.json`、`requirements-test-matrix.json`與`fault-recovery-matrix.json`。

參考現成方法：SQLite WAL讀取快照／savepoint、Python contextmanager與ParamSpec；演算法驗證用小規模窮舉對照最佳指派和手算聯合區間，沒有重造資料庫或連接付費模型。參考 https://sqlite.org/isolation.html 、https://docs.python.org/3/library/contextlib.html 、https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html 。
'''
(F/'FINAL_REPORT.md').write_text(report)
progress=load(F/'PROGRESS.json');progress.update(status='LOCAL_SCOPE_COMPLETE_WITH_REMOTE_GATE_BLOCKED',phase='All local execution/triage complete; committed recovery package must still be exported and restored',completed_at=now,original_diagnostics=11798,diagnostic_statuses=counts,unreviewed=0,confirmed_defects=10,fixed_defects=10,open_confirmed_defects=[],final_regression=full,stock_gui_final=stock,native_gui_final=dict(status='PASS',cases=19,images=11,source_unchanged=True),latest_new_review=dict(unique_current_occurrences=union_count,new_or_variant=new_count,unreviewed=0),next='Commit final docs/checkpoint; export_local_delivery.py; verify receipt and clean Git. Do not expand scope or push unknown fee triggers.',final_delivery_status='CHECK_POST_COMMIT_RECEIPT_OR_ZIP_RESTORE_RECEIPT',remote_write='NOT_PERFORMED_COST_UNKNOWN');save(F/'PROGRESS.json',progress)
state_path=ROOT/'docs/dev/STATE.json';state=load(state_path);state.update(active_task='PRE_DOWNLOAD_AUDIT_LOCAL_COMPLETE',audit_plan_status='LOCAL_SCOPE_COMPLETE_WITH_REMOTE_GATE_BLOCKED',audit_final_report='docs/dev/pre_download_audit/FINAL_REPORT.md',audit_final_checkpoint='docs/checkpoints/CP-20261020-AUDIT-LOCAL-FINAL.json',audit_source_commit=source,audit_recovery_receipt='.cache/debug-tooling/audit-delivery-20261020/receipt.json',next_tasks=['Preserve/download local audit recovery ZIP; verify manifest base/head and restored receipt.','Resume only the next authorized work or safe offline Windows/user report; do not auto-start EXE/web/mobile/whole-repo type cleanup.','Remote persistence/formal evidence requires verified zero-new-cost trigger information; do not push/PR/CI or claim REMOTE_VERIFIED without it.']);save(state_path,state)
plan_path=ROOT/'docs/dev/PRE_DOWNLOAD_AUDIT_PLAN_20261020.json';plan=load(plan_path);plan.update(status='LOCAL_SCOPE_COMPLETE_WITH_REMOTE_GATE_BLOCKED',scope='PRE_FIRST_DOWNLOAD_AUDIT_EXECUTED_LOCAL_SCOPE',completion_report='docs/dev/pre_download_audit/FINAL_REPORT.md',source_commit=source,completed_at=now,qualification='Local available-condition execution complete; external/native/real-corpus and current formal remote evidence qualifications unchanged')
for phase in plan['phases']:phase['status']='LOCAL_COMPLETE';phase['external_qualifications_unchanged']=True
save(plan_path,plan)
f=ROOT/'docs/dev/PRE_DOWNLOAD_AUDIT_PLAN_20261020.md';f.write_text('> 最新結果：本機範圍已完成；1921PASS、原版27GUI作業PASS、實際桌面19項PASS。正式遠端治理仍阻擋，沒有推送。詳見[完成報告](pre_download_audit/FINAL_REPORT.md)。原計畫與資格限制保留如下。\n\n'+f.read_text())
f=ROOT/'docs/dev/ACTIVE_DEVELOPMENT_HANDOFF.md';text=f.read_text();at=text.index('## 產品GUI交接');f.write_text(f'''# 最新接手：本機全面查證完成，遠端治理仍阻擋

先讀pre_download_audit/FINAL_REPORT.md與PROGRESS.json。本輪來源{source}，1921PASS/{full['healthy_modules']}健康/0runtime/原1850保留，新71有意義案例；27原版GUI作業PASS、native00519PASS/11PNG。10類共通根因已修，原11798診斷0未審，原指紋/次數與證據引用完整；9187型別契約、1856工具限制、740已修連動、15外部阻擋。最後兩profile union{union_count}、新增/變體{new_count}均判讀；完全重複7未增加、近似{clone_count}均審，4低優先候選保留。817/825條款有測試連結，8原PARTIAL/DEFERRED原因逐條保存，不提高真實資格。

Source read-view94PASS，最後7含巢狀/例外pending write與ParamSpec隔離錯型別示範均PASS。full0051886是歷史版本；006273/007637/008115/009848中斷、無效fixture/錯cwd/297錯座標證據皆保留，不算完整成功。最新完整只有full010。原172需求166明列範圍/3部分/3延後、75父題、AI8包50條真實資格8部分/0完整不變。

還原交付：.cache/debug-tooling/audit-delivery-20261020/receipt.json與ZIP。只有receipt或ZIP內RESTORE_RECEIPT標記LOCAL_SAVED_AND_RESTORE_VERIFIED才代表匯出/隔離還原完成；精確base/head看manifest。使用者應保存ZIP，沒有推送GitHub。正式治理因歷史source evidence過期FAIL；新正式run缺真實GitHub來源讀回，不偽造、不關Gate、不得REMOTE_VERIFIED。無新收費功能/API/試用/runner/子代理，帳戶帳單未核對；零新增費用優先。私人作品/字型/DB/模型留本地。下一步僅接續新授權工作或使用者本地安全報告，不自動EXE/前端/全庫型別整改。

'''+text[at:])
f=ROOT/'AGENTS.md';text=f.read_text();start=text.index('見[掃描與修正計畫]');end=text.index('使用者後續修正單一Codex限制',start);text=text[:start]+'''本機全面查證已完成，見[完成報告](docs/dev/pre_download_audit/FINAL_REPORT.md)、STATE與精簡交接。來源見完成報告：1921PASS/原1850保留/0runtime，27原版GUI作業與19實際桌面項目通過；原11798及最後新增/變體均判讀，基準未刷新。外部Windows/真實作品/印刷資格不變。正式遠端治理仍因來源讀回及費用證據不足阻擋；不得REMOTE_VERIFIED。使用者須保存本機還原ZIP，receipt/manifest為準；沒有自動EXE/網頁/手機/全庫整改授權。下文DEV-QUALITY-001為先前建置歷史，不代替本輪查證結果。

'''+text[end:];f.write_text(text)
f=F/'README.md';text=f.read_text();f.write_text('最新：本機範圍完成，先讀[FINAL_REPORT](FINAL_REPORT.md)、PROGRESS與還原receipt；正式遠端治理仍阻擋，沒有推送。本目錄也保留歷史失敗/中斷/拒絕證據，不能把任意歷史目錄當最後版本。\n\n'+text)
f=ROOT/'docs/dev/WORK_LOG.md';f.write_text(f.read_text()+f'\n{now} PRE-DOWNLOAD-AUDIT本機完成：source{source}，1921PASS/{full["healthy_modules"]}健康/0runtime/原1850保留；stock27、native19/11PNG通過。原11798與{new_count}新增/變體0未審；完全7/近似{clone_count}均判讀。10根因修復，8外部/延後條款不提高資格。正式治理仍FAIL來源過期/缺真遠端讀回；不push/PR/CI、不新增付費能力。最後提交後匯出並隔離還原ZIP，receipt為準。\n')
files=['docs/dev/pre_download_audit/FINAL_REPORT.md','docs/dev/pre_download_audit/PROGRESS.json','docs/dev/pre_download_audit/ledger-integrity-final.json','docs/dev/pre_download_audit/full-regression-final-010/summary.json','docs/dev/pre_download_audit/gui-stock-captures-final-003/summary.json','docs/dev/pre_download_audit/native-gui-final-006/native-runner-result.json','docs/dev/pre_download_audit/release-diagnostic-comparison.json']
save(ROOT/'docs/checkpoints/CP-20261020-AUDIT-LOCAL-FINAL.json',dict(id='CP-20261020-AUDIT-LOCAL-FINAL',phase='PREPARED',kind='LOCAL_SELF_VERIFIED_NOT_REMOTE',source_commit=source,summary='Available local audit complete; recovery exporter still must produce verified receipt. Formal remote qualification blocked and external statuses unchanged.',files=[dict(path=x,sha256=hashlib.sha256((ROOT/x).read_bytes()).hexdigest()) for x in files],remote_write=False))
print('Final local report/checkpoint prepared; commit and restore-verify package next')
