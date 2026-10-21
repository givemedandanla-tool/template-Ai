# Actual Windows build only; source and final executable independently checked.
$ErrorActionPreference = 'Stop'
if (!$IsWindows) { throw 'A native Windows runner is required' }
New-Item -ItemType Directory -Force artifacts | Out-Null
python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Pinned dependency installation failed' }
python -m pip freeze | Out-File -Encoding utf8 artifacts\installed-dependencies.txt
python tools/dev_governance.py check --require-evidence --publication-scope | Tee-Object artifacts\governance-gate.json
if ($LASTEXITCODE -ne 0) { throw 'Same-source full regression/evidence gate failed; do not build a release' }
python -c "import platform; from PySide6.QtWidgets import QApplication; from PySide6 import __version__; a=QApplication([]); print(platform.platform()); print('PySide6', __version__); print('Qt platform', a.platformName())" | Tee-Object artifacts\WINDOWS_RUNTIME.txt
if ($LASTEXITCODE -ne 0) { throw 'Native Windows Qt runtime failed' }
$windowsScope = Get-Content .github/windows-release-test-scope.json -Raw | ConvertFrom-Json
$auditArgs = @('docs/dev/pre_download_audit/run_local_audit.py', '--output', 'artifacts/source-tests', '--workers', '2')
foreach ($testModule in $windowsScope.modules) { $auditArgs += @('--module', $testModule) }
python @auditArgs
if ($LASTEXITCODE -ne 0) { throw 'Source regression failed; failures retained' }
python tools/windows_release.py spec
if ($LASTEXITCODE -ne 0) { throw 'Release specification failed' }
python -m PyInstaller --noconfirm --clean build/release/TemplateAI.spec *> artifacts\pyinstaller.log
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed; inspect pyinstaller.log' }
python tools/windows_release.py exercise --executable dist/TemplateAI/TemplateAI.exe --output artifacts/package-check
if ($LASTEXITCODE -ne 0) { throw 'Actual frozen executable acceptance failed' }
python tools/windows_release.py package
if ($LASTEXITCODE -ne 0) { throw 'Package inventory/checksum generation failed' }
