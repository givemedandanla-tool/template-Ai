# 匿名 PDF 嵌字授權核對與上傳中斷

自動審查拒絕 RUN-SEMANTIC-INDEX-001 PDF 的 GitHub blob，理由 NotoSansCJK 是受限字型。沒有嘗試繞過或改用另一上傳通道。先核對本機實際 `pdffonts`：兩檔均只有 NotoSansCJKtc-Regular；系統 fonts-noto-cjk copyright 明確 SIL Open Font License 1.1，原字型涵蓋 Files:*。其授權文字允許 embed；官方 [OFL FAQ 1.12](https://openfontlicense.org/ofl-faq/) 允許文件完整或子集嵌字。

`pdf-font-license-check.json` 提供具體 PDF hashes、pdffonts、系統 copyright hash，`noto-cjk-copyright.txt` 保存開源授權文字，不含字型二進位檔。AGENTS 的「受限字型」排除與 EVIDENCE_DESIGN 的「匿名 PDF」並存；這兩件僅為匿名合成輸出、可嵌入的開源字型，不含私人受限字型原檔。此為具體低風險核對，將僅有限重試同一 action；再拒絕仍保持阻塞，不冒稱遠端完成。
