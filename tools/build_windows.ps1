# 在 Windows Python 3.11 環境打包；保留動態 Qt 函式庫與授權文件。
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force artifacts | Out-Null
python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
python -c "import platform; from PySide6.QtWidgets import QApplication; from PySide6.QtGui import QFontDatabase; from PySide6 import __version__; app=QApplication([]); print(platform.platform()); print('PySide6', __version__); print('Qt platform', app.platformName()); print('Font families', len(QFontDatabase.families()))" | Tee-Object -FilePath artifacts\WINDOWS_RUNTIME.txt
if ($LASTEXITCODE -ne 0) { throw 'Windows Qt runtime diagnostic failed' }
python -m unittest discover -s tests -v 2>&1 | Tee-Object -FilePath artifacts\TEST_RESULTS.txt
if ($LASTEXITCODE -ne 0) { throw 'Acceptance tests failed' }
python -m PyInstaller --noconfirm --clean --onedir --windowed --name TemplateAI-v0.1 app.py
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed' }
Copy-Item docs\FIRST_VERSION.md dist\TemplateAI-v0.1\操作說明.md
Copy-Item docs\THIRD_PARTY.md dist\TemplateAI-v0.1\第三方授權.md
Copy-Item -Recurse examples dist\TemplateAI-v0.1\examples
$exe = (Resolve-Path dist\TemplateAI-v0.1\TemplateAI-v0.1.exe).Path
$capture = Join-Path (Get-Location) 'artifacts\windows-startup.png'
Remove-Item $capture -ErrorAction SilentlyContinue
$process = Start-Process -FilePath $exe -ArgumentList '--data-dir artifacts\package-smoke --capture artifacts\windows-startup.png' -PassThru
if (!$process.WaitForExit(60000)) {
  Stop-Process -Id $process.Id -Force
  throw 'Packaged startup exceeded 60 seconds'
}
$process.Refresh()
if ($process.ExitCode -ne 0) { throw 'Packaged startup failed' }
if (!(Test-Path artifacts\windows-startup.png)) { throw 'Packaged GUI capture missing' }
Compress-Archive -Force dist\TemplateAI-v0.1 artifacts\TemplateAI-v0.1-Windows.zip
Get-FileHash artifacts\TemplateAI-v0.1-Windows.zip -Algorithm SHA256 | Format-List | Out-File -Encoding utf8 artifacts\SHA256.txt
