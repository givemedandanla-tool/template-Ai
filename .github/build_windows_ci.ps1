# CI-specific Qt process isolation; product and original unittest cases unchanged.
param([switch]$NativeTestsOnly, [switch]$FrozenProbeOnly)
$ErrorActionPreference = 'Stop'
if (!$IsWindows) { throw 'A native Windows runner is required' }
New-Item -ItemType Directory -Force artifacts | Out-Null
# Python may inherit an 8.3 user-profile TEMP alias on hosted Windows. Use a
# canonical, short runner scratch path so literal fixture-path comparisons do
# not confuse RUNNER~1 with runneradmin. Original test methods remain unchanged.
$testScratch = Join-Path $env:RUNNER_TEMP 'template-ai-ci'
New-Item -ItemType Directory -Force $testScratch | Out-Null
$testScratch = & python -c "from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())" $testScratch
if ($LASTEXITCODE -ne 0) { throw 'Cannot canonicalize the isolated test scratch directory' }
$env:TMP = $testScratch.Trim()
$env:TEMP = $env:TMP
python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Pinned dependency installation failed' }
python -m pip freeze | Out-File -Encoding utf8 artifacts/installed-dependencies.txt
if (!$NativeTestsOnly -and !$FrozenProbeOnly) {
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
if ($FrozenProbeOnly -and $env:FROZEN_UTF8_AB -eq 'true') {
    python docs/dev/releases/run_frozen_utf8_ab.py
    if ($LASTEXITCODE -ne 0) { throw 'Actual frozen UTF8 baseline/fixed comparison failed' }
    return
}
python tools/bundled_inkscape_build.py prepare
if ($LASTEXITCODE -ne 0) { throw 'Pinned bundled runtime preparation failed' }
python docs/dev/releases/add_inkscape_notices.py
if ($LASTEXITCODE -ne 0) { throw 'Original upstream dependency-license preservation failed' }
python tools/windows_release.py spec
if ($LASTEXITCODE -ne 0) { throw 'Release specification failed' }
python docs/dev/releases/configure_frozen_utf8.py
if ($LASTEXITCODE -ne 0) { throw 'Documented UTF8 interpreter configuration failed' }
python -m PyInstaller --noconfirm --clean build/release/TemplateAI.spec *> artifacts/pyinstaller.log
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed' }
python tools/bundled_inkscape_build.py install
if ($LASTEXITCODE -ne 0) { throw 'Bundled runtime installation failed' }
python docs/dev/releases/run_frozen_probe.py --executable dist/TemplateAI/TemplateAI.exe --output artifacts/package-check
if ($LASTEXITCODE -ne 0) { throw 'Actual frozen executable acceptance failed' }
# The original acceptance requires a new output directory. Preserve the build
# policy report only AFTER the original EXE exercise has created that directory.
Copy-Item artifacts/build-payload-filter.json artifacts/package-check/build-payload-filter.json -ErrorAction Stop
Copy-Item artifacts/dependency-license-verification.json artifacts/package-check/dependency-license-verification.json -ErrorAction Stop
Copy-Item artifacts/upstream-license-download.json artifacts/package-check/upstream-license-download.json -ErrorAction Stop
if ($FrozenProbeOnly) { return } # Diagnosis never tags/packages/publishes.
python tools/bundled_inkscape_build.py sources
if ($LASTEXITCODE -ne 0) { throw 'Corresponding-source asset preparation failed' }
python tools/windows_release.py package
if ($LASTEXITCODE -ne 0) { throw 'Package inventory/checksum generation failed' }
