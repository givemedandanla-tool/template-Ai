@echo off
setlocal
set "PYTHONUTF8=1"
chcp 65001 >nul
cd /d "%~dp0"
if not "%~1"=="" if /I not "%~1"=="--offline" (
  echo 用法：PREPARE_WINDOWS.bat，或 PREPARE_WINDOWS.bat --offline wheelhouse
  exit /b 2
)
if /I "%~1"=="--offline" if "%~2"=="" (
  echo 離線準備需要已備妥的 Windows Python 3.11 套件資料夾。
  exit /b 2
)
if not exist .venv\Scripts\python.exe (
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo 尚未建立本機環境。請先安裝 64 位元 Python 3.11 與 Python Launcher。
    echo 不需要系統管理員權限；請選擇安裝到自己的帳號。
    pause
    exit /b 2
  )
)
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_NO_INPUT=1"
set "PIP_REQUIRE_VIRTUALENV=1"
if /I "%~1"=="--offline" (
  .venv\Scripts\python.exe -c "from template_ai.offline_runtime import assert_local_path; import sys; assert_local_path(sys.argv[1])" "%~2"
  if errorlevel 1 (
    echo 離線準備只接受本機套件資料夾，請勿使用網路磁碟或網址。
    pause
    exit /b 2
  )
  echo 只使用指定的本機套件資料夾，不連線下載。
  .venv\Scripts\python.exe -m pip install --no-index --find-links "%~2" -r requirements-lock.txt
) else (
  echo 首次準備：這一步會下載 requirements-lock.txt 指定的套件到本專案 .venv。
  echo 日後請使用 START_WINDOWS.bat，啟動時不會再下載套件。
  .venv\Scripts\python.exe -m pip install -r requirements-lock.txt
)
if errorlevel 1 (
  echo 首次準備尚未完成。請確認套件來源、Python 版本與可用磁碟空間後重試。
  echo 軟體未啟動；這不會刪除你的私人資料。
  pause
  exit /b 2
)
.venv\Scripts\python.exe tools\local_start.py --check
set "TEMPLATE_AI_EXIT=%errorlevel%"
if "%TEMPLATE_AI_EXIT%"=="0" echo 首次準備完成。日後雙擊 START_WINDOWS.bat 即可離線啟動。
pause
exit /b %TEMPLATE_AI_EXIT%
