# 當前：UI061 全20條款實作待驗證，接續 UI062；歷史12/28

- Branch dev/v0.1-first-version / PR #2。零例行問題；按需 rg、工具輸出≤1600 tokens；每可恢復階段/10min checkpoint +GitHub逐檔回讀。不開 agents/EXE/paid service，不合併 main。最新收據由 STATE.last_confirmed_checkpoint 指向。
- 契約 FIXED70_REMAINING28_CONTRACT.json，28原父題不能用子項冒充。歷史完成 UI046/047/049/050/051/052/053/054/055/056/057/058 共12/28、120原條款。LAYOUT003原來源8423924：1078/1078、140modules、capture0、204附件GitHub發布406699e、Gate169/150scoped PASS。所有舊 finalizer 已執行，禁止重跑。來源修改後原claims均重新開啟pending，不沿用舊PASS作新證據。
- UI059原10/UI060A原6/UI061原20已完整實作/coverage登錄，但 pending 全來源不可變回歸+原生截圖逐張review+普通GitHub發布Gate。歷史12數字維持，不把targetPASS算父題完成。
- UI059：NetworkX依賴DAG、既有singleworker prepare/calc/install、人工delta/20history/singleundo/context和ABA柵欄、非正式比較+明確採用、currentwholecard。47newtests。UI060A：當前合格有限scope推薦、多候選比較、typed問題定位、尺寸/人工版本變更不能正式輸出。19newtests。詳各EXECUTION_PLAN/CLAUSE_COVERAGE。
- UI061：57newtests。精確source entity/field joins；各候選/尺寸幾何與鎖定獨立；明確align/color/locked跨目標預覽/確認/逐項安全採用；不複製coords/font/owner。來源同步保留人工geometry，舊相同字串新實體不繼承；來源undo先列真正影響候選，草稿直到adopt不動global；existingMultiSize/Main worker，不新建queue/DB。詳UI061_EXECUTION_PLAN/CLAUSE_COVERAGE。
- 真實錯誤保留：031兩項FAIL證明同名字串wrong-company Logo與刪binding曾繞過Gate；修正使用既有LogoStore.match實體/尺寸/selected_id，calc+outputrevalidate+common candidate_risk CURRENT_LOGO_IDENTITY均核對。03234PASS；0342PASS專測直接placedLogo與cross dependency floor、補綁只清derivedgap不洗掉人工UNKNOWN。沒有stable root的legacycaller mapping不聲稱有ID檢查。
- Native030實際13畫面PASS/0Qt，已逐張開啟review/hash於ui061-native-030-visual-review.json；晚於030的identity修正需正式batch重新capture。tools/capture_sync_workflow.py已接run_evidence：實際兩人兩公司三候選二尺寸/同電話不串人/人工A移動/跨B成功C100missingLogo失敗保留/SourceUndoimpact/90FINAL PNG與100PREVIEW分開輸出。私有Illustrator/指定Windows host資格沒有被合成Linux樣本取代。
- 下一步：UI061 coherent affected tests保存獨立log並修真fail，checkpoint後UI062按原契約導航/安全返回；持續完成UI063/064/065/052-REVIEW/019/032/031/066/067/REV01/02/04。多父題批次後再immutable全run；舊runs/PIDs都不重用。snapshot前要等待自己啟動的test/capture真exit，不能讓log在prepare後繼續寫入。
- 時限：先前Logo身分診斷/修正超過10min，strict checkpoint cadence不是PASS；偏差記錄留STATE/history，不抹除。
- 詳細歷史：history/HANDOFF_BEFORE_UI061_FULL20_20261016.md；更早layout002/003及UI059等見history，按需讀，不全展開。

UI061 coherent037：163tests/17modules 全部PASS，0skip/Qt；full20 mapping及runner capturehook就緒，下一項UI062。
