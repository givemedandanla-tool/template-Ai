# CORE-037／038／039：安全多選、共同屬性與精確幾何整包契約

2026-10-14；從已保存OBJECT_TOOLS_NEXT_PLAN與原UI_DECISIONS UI034／035／036接續。一般實作選擇：既有訓練／模板工作台開啟同一套進階物件編輯器，畫布、複選清單與屬性面板共用stable-ID集合；保留原單選編輯操作且所有途徑受鎖定policy保護。來源原生圖層／文字未知仍未知，不另猜AI層級，不將本Linux匿名包當全部父題或獨立品質驗收。

## 範圍與不可降低的驗收

CORE-037：實際兩模式入口，中央畫布click／modifier多選／框選、清單複選／解除、面板同一集合與定位；切／重排不誤選人。單選來源／kind／owner／共享關聯／lock／模板尺寸／mm rect／font／style／fixed pt／min_scale／align／color／required可讀；未核對原生文字及字距明示未知。多選共同可編輯屬性、混合標示、只提交明確dirty字段，未dirty／未選欄不變；不同owner／Logo混合顯示適用限制與明確跨owner確認，不能把第一個值複製給全部。實際GUI／多選與未dirty保護具名證據。

CORE-038：Slot.locked預設False相容既有資料，獨立明確鎖定／解鎖及逐對象scope。鎖定擋拖曳／精確值／批次patch／幾何／刪除及字型替代；混合選到locked不偷偷排除後稱整組成功。已發布唯讀、原稿readonly；主編輯既有操作、Library一般save／source標記、字型新草稿交易也不能繞過lock。新版本保留lock，Undo明列lock變動，不因hide／selection退出Gate。真實主窗口／DB途徑與legacy具名測試。

CORE-039：明確reference(指定物件或選取邊界)，六方向對齊／水平垂直邊界間距等距／整體mm位移。只改已選x/y、不改w/h／pt／font/style／scale／align／Logo比例／owner／未選。差異canvas及table有old/new、delta、scope、reference／gap／collision／bounds，取消不寫；拖曳也先候選再明確套用。對整包原子保存、audit與可追溯edit clock；persistent Undo／Redo重開可用，hash＋單調clock擋後續保存、發布、ABA／stale及全批晚期失敗rollback。訓練作品以精確revision保存，變形修改撤銷舊visual_confirmed，原檔／發布版本不改。不合格草稿明示可修，既有publish／formal export Gate不降。預覽未提供實際人物文字的readability仍待排版，不冒稱完整字形／原稿視覺驗證。

## 算法與選型

參考商用Illustrator Align的明確key object／selection基準與spacing；開源Qt QGraphicsItem／QGraphicsScene選取、itemChange防移動與model/view的stable集合、Undo command概念。不複製第三方碼，已有Qt／SQLite滿足，不新增大型依賴。

對齊left/right/center、top/bottom/center由reference邊界／中心減本rect寬高得到；排序(x或y,stable ID)。等邊界間距固定最外兩端，gap=(span−sum(size))/(n−1)；累加每個自身size＋gap，負gap明示。group move每個rect加同一(dx,dy)，手算不依像素倍率。最多200 objects／50本機歷史展示，不能用隱藏減少驗證。未選reference／非finite／duplicate或不存在ID／跨owner未確認／鎖定／不適用屬性／Logo不等比均有明確錯誤，不寫DB。空patch／無差異不建假歷史。

GUI用普通immutable request＋完整base fingerprint／db revision，Library鎖內重算request不信任回傳after。persistent object_edits保留exact before/after、scope／operation／revision／warnings與phase；UndoRedo鎖內CAS，audit failure全rollback。單純檢視不寫歷史。主窗口未保存內容／未提交屬性不被進階工具丟棄；錯誤後controls恢復與可重試。傳統Undo入口也要拒絕stale／published／locked；新整包Undo走明列範圍的persistent歷史。

## 證據計畫

獨立手算六方向／兩軸gap／same-position stable順序／move；多owner與shared logo／非法與locked集合；混合dirty欄位、Logo比例、未選pin/style/pt不變；duplicate/old-schema；實際QTest畫布／list／props三向、拖曳預覽取消、發布唯讀、兩模式入口；Library late-audit rollback、template ABA與source revision、重開UndoRedo與後續更改拒絕；真GUI整包apply/history／retry與候選stale。正式全回歸＋anonymous multi-selection／mixed面板／差異／lock／history截圖、機器old/new scope／gap報告，固定source commit/tree，附件／收據Github逐檔讀回。

以下是预计具名測試方向，完成測試後將具體IDs登錄機器acceptance；未執行不能完成：test_object_tools.ObjectToolsTests（math／scope／persistence／lock）；test_object_tools.ObjectToolsGuiTests（3way／mixed／drag／two-modes／retry/stale／actual workflow）。

不打包EXE；UI048最後、印刷與指定hardware／真實AI／Windows／獨立覆核保持待驗。新39個CORE只代表已拆分清單，剩餘父需求仍需再拆分，不拿0未登錄CORE當產品已完成。
