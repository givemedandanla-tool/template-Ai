# 下一完整大工作包：三向安全多選與精確對齊

2026-10-14；狀態PLANNED，尚無本包完成宣告。已讀docs/UI_DECISIONS.md UI-034／035／036全部原條款與目前GUI：slot_list.currentRowChanged僅單選、Canvas／Box與make_slot整組回填。繼續既有全清單目標，開始code前另建CORE登錄／具名驗收及BEGIN，不覆寫這輪對照FINAL快照。

## 大包範圍與順序

1. 選取集合使用stable slot_id，畫布框選／清單多選／屬性面板三向同步；解除、重排及切模式不誤選另一人物／公司。不做不可核實原生Illustrator圖層推定。
2. Slot.locked default False相容舊資料，個別及明確群組鎖定／解鎖；中央policy擋拖曳、精確數值、多選、刪除、吸附、對齊等變更。鎖定不是隱藏，不降低發布／輸出Gate。
3. 共同屬性只提交明確dirty patch。混合值顯示混合，未修改欄位不從第一個物件複製；Logo／一般文字／不同owner／共享關聯混合，列出適用與不適用。幾何操作維持font pin／style／固定pt／align／color／owner／index／Logo整體比例與未選物件。
4. 明確指定物件或選取邊界為基準，六方向對齊、邊界間距等距分布、整體mm位移；排序穩定，用物件ID消除同座標次序不確定。不能默選基準或默默排除鎖定／不適用物件後稱全組成功。
5. 真正差異疊圖及位置／位移／基準／間距／碰撞／邊界摘要，預覽可取消且不寫內容。核對精確範圍後原子套用；Undo／Redo可核對且不能覆盖後續編輯／發布。既有主編輯與Library版本clock／CAS協作，儲存失败不丟手工內容。
6. 套用後所有slot重新驗證；草稿可明示不合格供修復，發布／正式輸出不放寬。視圖篩選不能使真實未顯示物件退出驗證。原檔及發布模板不覆寫。

## 數學與可覆核證據

六方向以reference邊界／中心計算每個rect的x或y，不改w／h。等邊界間距：排序後固定最外側端點，gap=(總span−sum(widths))/(n−1)，新x逐段累加自身width＋gap；垂直對應。負gap／越界如實顯示，不偷偷縮小文字／Logo或調字級。群組位移每個已選rect加同一(dx,dy)，內部相對位置保持。

具名測試須用獨立手算oracle、重複ID／跨owner／共享Logo／locked混合、同座標次序、畫面倍率不改mm、混合patch不覆蓋未dirty值、真Qt框選／清單複選／面板同步、預覽取消、原子rollback、UndoRedo／後續clock變化、发布保护与旧模板兼容。保存真實匿名多選／差異畫布／混合面板截圖与機器前後positions／scope報告；source commit/tree／個別JUnit／附件讀回。獨立品質、真實原生來源／指定hardware不拿Linux合成PASS替代。

開始時讀既有editing undo及save/publish路径，列出CORE契約與test IDs，再建baseline／BEGIN與GitHub讀回；此文件是下一包具體分析／計畫，不替代實作或原75父題全部條款。
