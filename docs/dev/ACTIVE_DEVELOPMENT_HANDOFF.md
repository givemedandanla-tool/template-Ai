# 當前：OCR beta.2第五輪Windows驗證

精確sourcef1a38ba7c6164a46209a6198aa6f83997720650c／run40056934391。beta.2未發布、beta.1保留。代碼/來源全凍結並推feature/exactrequest；本輪修正Windows受驗model短暫存及source fault ownedcopy。

最新本機回歸75PASS（resolver19/session32/Logo6/analysis10/GUI8，內含真GUI35checks），另obsnegativeguard18PASS。Win把選中模型原bytes複製到owned短temp，原/副SHA、BUNDLE官方blob驗證，不換模型；child停止才清理。SOURCE_EXTERNAL自選模型仍保留原bytes。受控MODEL/IMAGE/PROCESS錯碼不帶private stderr。圖片維持STDIN_BINARY_IMAGE，pixels/psm/中文條件不變。

source負向probe先正式驗真stage，再copy到本次SYNTHETIC_ONLY/.../engines/tesseract並照pin全驗，僅隔離副本exe、finally還原env；frozen仍物理驗真正包內engines/tesseract、hostguard不放寬。

第四run40055712702/source9fd9d9db：263項261PASS/1failure/1error/0skip/timeout，Windows精確英/繁中SVG＋點陣PDF及owner人工保存重開已PASS（stdin修通原CLI exit1）；剩深中文modeldir與CI sourceguard，皆本輪處理。此前sourcec46原先兩媒體CLIexit1（非錯字）、source576 PDFhandle已QBuffer修、source6e62缺zstd/build/LICENSE已精確追蹤75/75。原始失敗保留版本目錄。

下一步所有source→真EXE包內雙語雙媒體、實體缺/壞人工退路→原private payload gate→六附件草稿/公開兩次逐檔及25sourceZIP內檔驗證→finalcheckpoint+原生Git讀回才交付。失敗讀review-release-evidence/v0.1.0-beta.2/runs/40056934391-1-f1a38ba7c616小型JSON/log。

runtime107entries+manifest108files，source25archives260799778bytes與75notices，原模型單份engines/ocr-models；新增sources ZIP另附。GitHub短暫401已實際恢復。main、私人資料、原未提交timeout/adopt成果不變；無新付費API/資源。
