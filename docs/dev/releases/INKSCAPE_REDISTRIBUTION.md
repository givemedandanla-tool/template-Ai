# 隨包 Inkscape 1.4.2：授權、來源與重建

隨附官方 Windows x64 Inkscape 1.4.2（ebf0e94，2025-05-08），以獨立程序執行，沒有修改其二進位。執行時不下載工具、不改用系統安裝版。私人作品、個人字型、資料庫不包含在發佈包。

官方完整二進位依其 share/inkscape/doc/COPYING 為 GPL-3.0-or-later；個別來源檔與相依元件依各自授權。包內保留 COPYING、LICENSE、AUTHORS 及各元件聲明。這個獨立程序的合併散佈不表示更改 Template AI 其他部分的授權。Inkscape 不對使用者製作的作品主張其程式授權。

包內 TEMPLATE_AI_DEPENDENCY_LICENSES 另保留官方精確 IDW r88 環境的原始授權檔位元組，包含部分只用於建置的元件聲明，不代表全部功能都啟用。來源環境 SHA 及實際檔案數寫入 SOURCE.json 與發佈驗證；解壓前先核對完整環境封存檔 SHA，不由文字報告猜測還原授權檔。

同一 GitHub Release 免費提供 inkscape-1.4.2-corresponding-sources.zip。日常操作只需下載 Windows 程式 ZIP。來源附件含 Inkscape、四個精確子模組、官方自編 GraphicsMagick 1.3.43、117個 MSYS2 對應來源包、精確建置腳本，共125份來源物件，不只是網址。SOURCE_MAP.json 記錄公開出處、大小及 SHA-256。MSYS2 .src.tar.* 包含 PKGBUILD／補丁／上游來源，各包保留自己的授權。

重建引擎：解開各來源包，依 PKGBUILD／上游 INSTALL／官方 Inkscape README、buildtools/msys2installdeps.sh 與 IDW r88 .gitlab-ci.yml 建置。主樹四個 gitlink 不含內容，將 map 中 extensions、themes、lib2geom、libcroco 精確來源放回 share/extensions、share/themes、src/3rdparty/2geom、src/3rdparty/libcroco。IDW r88 使用另附的 0ccb00a… 版安裝腳本，自編 GraphicsMagick 的指令為 ./configure --enable-shared && make && make install。本專案未宣稱已從來源重建出逐位元相同的官方執行檔。

重建 Template AI：使用該 Release tag 的完整倉庫、Python3.11及 requirements-build.txt；先準備完整引擎目錄與 manifest，再用 tools/windows_release.py spec、docs/dev/releases/configure_frozen_utf8.py、PyInstaller 建置。官方發佈使用 tools/bundled_inkscape_build.py 和 tools/inkscape_distribution_lock.json，只接受鎖定的官方元件。自行修改引擎時，在自己的來源副本重新產生 manifest 與 release-info.json 中的 manifest SHA，再重新打包自己的版本。沒有簽署鎖、遠端授權或禁止修改的金鑰；雜湊防止解壓不完整與版本混用。不要冒用官方已驗證 tag／版本，亦不要改掉已確認稿的環境資格。

程式與來源附件免費取得位置：
https://github.com/givemedandanla-tool/template-Ai/releases

本次保存完整來源、授權與重建線索，不將私有格式支援或實際作品品質宣稱為完全還原。
