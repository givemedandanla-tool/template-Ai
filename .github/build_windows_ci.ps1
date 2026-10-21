# CI-specific Qt process isolation; product and original unittest cases unchanged.
param([switch]$NativeTestsOnly, [switch]$FrozenProbeOnly)
$ErrorActionPreference = 'Stop'
if (!$IsWindows) { throw 'A native Windows runner is required' }
New-Item -ItemType Directory -Force artifacts | Out-Null
python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Pinned dependency installation failed' }
python -m pip freeze | Out-File -Encoding utf8 artifacts/installed-dependencies.txt
if (!$NativeTestsOnly) {
    python tools/dev_governance.py check --require-evidence --publication-scope | Tee-Object artifacts/governance-gate.json
    if ($LASTEXITCODE -ne 0) { throw 'Current-source permanent evidence gate failed' }
}
python -c "import platform; from PySide6.QtWidgets import QApplication; from PySide6 import __version__; a=QApplication([]); print(platform.platform()); print('PySide6', __version__); print('Qt platform', a.platformName())" | Tee-Object artifacts/WINDOWS_RUNTIME.txt
if ($LASTEXITCODE -ne 0) { throw 'Native Windows Qt runtime failed' }
if (!$FrozenProbeOnly) {
$scope = Get-Content .github/windows-release-test-scope.json -Raw | ConvertFrom-Json
$auditArgs = @('docs/dev/releases/run_windows_case_audit.py', '--output', 'artifacts/source-tests', '--workers', '1')
foreach ($testModule in $scope.modules) { $auditArgs += @('--module', $testModule) }
python @auditArgs
if ($LASTEXITCODE -ne 0) { throw 'Original Windows regression failed; do not package' }
}
if ($NativeTestsOnly) { return }
# Reuse the same packaging/spec, actual-EXE acceptance and download verifier.
python tools/windows_release.py spec
if ($LASTEXITCODE -ne 0) { throw 'Release specification failed' }
python -m PyInstaller --noconfirm --clean build/release/TemplateAI.spec *> artifacts/pyinstaller.log
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed' }
python docs/dev/releases/run_frozen_probe.py --executable dist/TemplateAI/TemplateAI.exe --output artifacts/package-check
if ($LASTEXITCODE -ne 0) { throw 'Actual frozen executable acceptance failed' }
if ($FrozenProbeOnly) { return } # Diagnosis never tags/packages/publishes.
python tools/windows_release.py package
if ($LASTEXITCODE -ne 0) { throw 'Package inventory/checksum generation failed' }
