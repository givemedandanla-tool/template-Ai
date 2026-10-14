# 版權／隱私問題事件紀錄報告

2026-10-14（Asia/Taipei）。依使用者修正後指令，記錄事件內容與解決方案；不把「授權替代」當成繞過審查或降低驗收的理由。沒有客戶DB、私人AI原稿、受限字型原檔上傳。

## E-001：匿名 PDF 被判定含受限字型

事件內容：第一包GitHub blob上傳被自動審查拒絕，指NotoSansCJK嵌字違反受限字型限制。當時完整证據checkpoint維持PREPARED，沒有冒稱遠端保存。

解決方案：對實際兩件PDF執行pdffonts，只發現NotoSansCJKtc-Regular；核對本機fonts-noto-cjk copyright、上游Sans/LICENSE及OFL FAQ1.12，SIL OFL1.1明確允許文件嵌字。保存授權文字／實際PDF hash；取得使用者對匿名PDF與GUI的明確核准，同API正常上傳及讀回。沒有重發字型原檔、改用受限字型或更換上傳通道。

證據：`docs/evidence/attempts/THREE-PACKAGES/pdf-font-license-check.json`、`noto-cjk-copyright.txt`、`PDF_LICENSE_CHECK.md`；上游 [Noto Sans LICENSE](https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE)、[OFL FAQ](https://openfontlicense.org/ofl-faq/)。第一／第二包PDF已保存，後續相同OFL字型按具體附件清單處理。狀態：授權風險已核對；不宣稱其他未知字型取得嵌字許可。

## E-002：PNG 未檢視及具體 payload 身份不清

事件內容：第一包某PNG被自動審查以未檢視可能含敏感資料拒絕。全部34PNG/JPG實際view_image後，仍要求具體使用者批准。使用者已明確核准第一包及後續兩包同匿名fixture GUI證據。

解決方案：保存每件file/hash與視覺檢視紀錄，內容只含公開固定示範Alex／Casey Example、示範林小明、0900電話及.test信箱、匿名stable IDs。收到批准後同GitHub API正常上傳；第一包201PASS／49附件全量讀回61f8c7e5。第二包216PASS／54附件全量讀回f656abcb。

證據：`semantic-publication-inspection.json`、`batch-publication-inspection.md`、`2026-10-14-EVIDENCE-SUBSTITUTION.md`及兩包REMOTE_VERIFIED收據。狀態：前兩包完整附件已解決；此前所有失敗／中斷原因保留。

## E-003：後續匿名回歸截圖被再次拒絕

事件內容：已取得後續同fixture批准，但上傳object-tools-training、semantic-tree-shared、multiple-artworks及object-tools-locked等回歸PNG，仍被判定二進位API參數沒有可核對檔名／用途或不能對應具體批准。部分獨立同API呼叫成功，其他已view_image並核對hash的呼叫仍拒絕；不能把不一致的審查結果當成全部已保存。

已嘗試方案：每件顯示實際檔名、bytes、Git blob SHA／SHA256，實際view_image，變成獨立單件正常API呼叫；只重用已成功的immutable blobs，回傳SHA必須匹配。一次低detail顯示格式不受平台支援而圖片未顯示，立即改high實際重看，不能把省略圖當檢視證據。曾因cell失聯使metadata helper回到舊版本，核對remote ref後恢复，沒有盲目重推或force。

目前解決路徑：固定`PUBLIC_EVIDENCE_APPROVAL_MANIFEST.json`列出兩次第三包run的90件具體PNG/JPG/PDF檔名／bytes／SHA256，約14MB，已將清單以code/docs-only提交e682b1b8讀回，提出更具體批准。只在批准抵達後重試相依binary動作；未完成的仍保留本機ZIP、完整hash及PENDING_REMOTE。不另換CLI／通道、不將被拒圖片轉藏在其他檔案，也不拿文件代替GUI證據。

狀態：截至本段保存，object-tools-locked.png等完整第三包附件仍受阻，兩次run的code／測試／JSON／JUnit已在GitHub。最終驗收結果以STATE與REMOTE_VERIFIED收據為準，取得批准或完成後追加結案記錄，不改寫這段歷史。

## 等效替代原則

使用者授權可用合法、自製合成或有明確許可的開源素材替代有版權／隱私風險者，也可採等效可驗證的方法；每次需記錄原事件、替代來源與許可、為何等效、差異與验收。真實來源未驗仍明示，不以合成例圖冒稱真實AI視覺一致。本輪沒有替換私人材料，處理的是已合成附件的授權／身份核對；沒有假稱任何未知原稿或商用字型合法。

## E-003 續記：已核准固定90件，API關聯仍間歇受阻

使用者已明確回覆「核准清單中全部90件具體附件」，不再記為缺少其授權。全清單本機bytes／SHA256／Gitblob匹配，並從GitHub immutable blob9426b2d8核對清單原內容。批次RUNNING、例外RESTORED及字型審核PNG各有同API具名檢視後成功；RESTORED回應parser修正後以新tree核對實際SHA997d29d6，PNG的UTF8 fetch限制不是審查拒絕。

仍有API呼叫以無檔名／SHA／manifest對應拒絕，雖然呼叫前均列出對應且部分逐張實際檢視。object-tools-difference最後呼叫被中止，停止盲目重試此檔。cell失聯有界恢復及批准blob清單持久化。保留歷史與原匿名位元；未轉藏圖片、未更換通道、未用替代文件冒稱GUI證據完成。截至恢復紀錄仍11件pending；詳見APPROVED_EVIDENCE_UPLOAD_STATE。需平台具體payload關聯問題解決才能完整結案，已完成不受阻的程式／測試／來源metadata保存。
