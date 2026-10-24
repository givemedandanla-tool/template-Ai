# 當前：OCR beta.2第三輪Windows驗證

最新source c46aaaa4ba0cb649feca0dc66d5a645681c027c2／run40054323702。新review-v0.1.0-beta.2未發布，beta.1保留。

第二run40053298537（576d17e）prepare/cache PASS，22模組260項：258PASS／1FAIL／1ERROR／0skip。PDF暫存清理WinError32，現fixture以QBuffer寫入／讀取並finally close/delete；真GUI未認出精確繁中字串，現只增加固定合成來源白名單之有界actualfield/previewhash/model/lang/runtime/TSVlineID診斷，原中文要求與產品演算法不變。16unit與35真來源GUI PASS。

下一步若第三run來源失敗，從review-release-evidence/v0.1.0-beta.2/runs/40054323702-1-c46aaaa4ba0c/source-tests/test_review_tool_gui.log讀ASCIIJSON實際兩媒體候選及TSV。語言排序已排除：review analysis固定chi_tra+eng。要分辨漏字／分行／預覽，不盲改模型／閾值或降低條件。PDF問題也須真Windows通過。

第一run缺固定空notice zstd/build/LICENSE，已精確納入Git，全75notice及identity423PASS；GitHub短暫401已實際read/push恢復。25corresponding sources／75notices與runtime107檔均固定，source附件實驗全驗。代碼/來源全已推feature＋exactrequest，原始失敗見版本目錄。

全source→真EXE包內英/繁中兩媒體+實體缺壞人工退路→原private包裝gate→六附件兩次真下載→finalcheckpoint/nativeGit讀回才交付。main、私人作品／字型／DB、原未提交timeout/adopt工作不變；沒有新增付費API或資源。
