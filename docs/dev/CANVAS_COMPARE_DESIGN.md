# CORE-035／036：來源與前後模板同步對照定位

2026-10-14（Asia/Taipei）；接續UI-006／031／033／037已核准對照，完整大工作包包含背景產生實際三視圖、幾何映射與共用唯讀同步畫布，整合逐欄字型審核。

## 參考

商用 [Acrobat Compare Files](https://helpx.adobe.com/acrobat/using/compare-documents.html) 的並排與差異定位；開源 [Qt QGraphicsView原碼](https://github.com/qt/qtbase/blob/6.8/src/widgets/graphicsview/qgraphicsview.cpp) 的scene/view與可逆transform及ScrollBar對應；[OpenCV affine transforms](https://docs.opencv.org/4.x/da/d6e/tutorial_py_geometric_transformations.html) 的座標換算思路。自行實作、不複製第三方碼，不引入以像素相似猜原生文字的註冊演算法。

數學：模板mm座標(u,v)、來源作品crop(c_x,c_y,c_w,c_h)、模板(W,H)，來源頁面座標x=c_x+u*c_w/W，y=c_y+v*c_h/H；反函數唯一且可核對。像素再按預覽page dimensions／pixel dimensions映射。三圖以同一模板mm scene domain顯示，source pixmap仿射到同域，zoom與center共享；只改視角，不改字級或模板。點陣來源未物理標定時，page位置標為參考單位／像素，不冒稱實測來源mm。

## CORE-035 實際來源與前後矩形渲染

使用精確template source_work_id／revision取得歷史crop／physical dimensions，核對來源id、所選頁、衍生cache metadata及image/SVG hashes；不用當前新標記冒充舊模板來源。未知來源、失聯、篡改、過大／無法解析、crop不合法、模板尺寸與歷史标定不符各自UNKNOWN／BLOCKED，不能借別來源。

背景只讀產生原稿參考、原模板已知文字及替代模板同文字的完整矩形圖。原模板與替代均相同背景／框位／Logo保護／固定pt／水平界限／align／color；仅本欄字型改變。未提供其他欄位文字就保留空框標記，不拿同一姓名填全部。原字型不可核對则原模板文字未知，不能fallback畫成假原稿；源點陣只是衍生參考，不宣稱原生可編輯性／原字型已識別。來源或背景或目標異動、背景工作期間新輸入／模板clock改變時，不發布過期畫面或核准。

模板圖片每張最多6MP，來源解碼12MP／48MB，單資產50MB／每輪64MiB檔案大小，最多200框視覺提示。原稿hash證據只證內容身份，不能代替真人視覺一致性。既有單行glyph核對與形狀度量仍是硬Gate，全文／來源原生資訊不足如實標示。

## CORE-036 同步視圖與審核整合

三個唯讀畫布與物件列表共用stable slot_id；選欄位同步高亮三圖並定位，點圖上的框也回列表；不存在／多義／不同模板id時不誤選其他人物。共同fit、zoom、pan與單欄定位；視窗尺寸改變亦保持同一center／倍率；fit原稿全頁保留作品邊界，來源未知不阻塞合法候選與草稿審核。只讀框不可拖動；不切成新的模板編輯操作，不依hide/filter减少驗證範圍。

從字型逐欄詳審可開啟此對照；查看三圖後再回原流程明確核准、勾選與最终確認，原有stale／CAS／票據保護不降標。舊草稿／發布／來源原檔、font pins／DB在對照與導航前後完全不變。僅 sourceunknown可保持候選高風險人工審核，source或target內容篡改則不以過期對照放行。

## 驗收与完成

獨立手算映射／反函數、不同crop／未標定raster／精確舊rev來源、实际像素與文字style/size/color、no fallback、来源／背景異動與預算、同步fit／pan／zoom／click選取／readonly、真實worker成功錯誤／retry／stale、審核入口與全流程，具名測試及正式必要回歸PASS。匿名三視圖／zoom定位截圖、原／後矩形PNG與機器映射報告永久GitHub保存，源碼commit/tree與附件逐檔讀回。完整父題與真實AI／Windows／硬體／獨立品質仍需別的验收，不因本包成功提前標全部完成。
