# 字串語意與模型能力界線

使用者要求：辨別郵件、社群ID、市內電話、手機、地址、職稱；詢問分析法則、AI模型與自主增加參數能力。

目前引擎為本機混合分析：Inkscape真實幾何→矩形包含與座標轉換→語意候選→逐作品品質／雜訊檢查→有效已授權TRAIN的幾何模板草稿。電話直接重用python-phonenumbers 9.0.16 / Google libphonenumber；保留地區與類型依據，不將國際固網／行動混合類型硬猜為手機。郵件、社群平台與URL、地址、職稱依有界Unicode文字與明確證據產生待審分類；未知文字不按位置猜姓名或職稱。

尚未接入GPT／Claude／預訓練神經模型。開發助理不等於產品中的AI引擎，無付費API或來源檔外傳。新增CharacterModel是字元Multinomial Naive Bayes，採Laplace平滑、特徵覆蓋與類間margin拒答；已測試，尚未有已訓練啟用且接入主管線的模型。UNCALIBRATED分數不假稱正確率或機率。

訓練只能從明確確認與另行授權SEMANTIC_CLASSIFICATION_LOCAL的文字樣本估計詞頻／特徵權重；既有GEOMETRY_TRAINING_LOCAL權利不可無聲擴張。可累積新特徵及候選，不能自行改程式、擴神經網路架構或未審啟用／發布規則。修正來源事實與批准通用規則是不同操作。

下一步：重用同一TrainingStore保存模型候選與樣本pins；訓練／留出按來源hash隔離；顯示各類分母、錯誤、未知率；模型啟用需獨立人工核對。正式來源回歸之前不把語意完整性或20個父題標完成。相關要求見SEMANTIC_FIELD_CONTRACT.json，工程參照及算法見TWENTY_ENGINEERING_BASIS.json。
