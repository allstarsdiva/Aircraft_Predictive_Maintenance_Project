param(
  [switch]$SkipPythonTests
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
  throw 'Project virtual environment is missing. Follow the clean setup steps in docs/REPRODUCIBILITY_AND_DEMO.md first.'
}

Push-Location $repoRoot
try {
  if (-not $SkipPythonTests) {
    & $pythonExe -m pytest -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed with exit code $LASTEXITCODE." }
  }
  & $pythonExe -m src.check_independent_validation docs/independent_validation_manifest_template.csv
  if ($LASTEXITCODE -ne 2) { throw 'Expected the empty independent-validation template to remain blocked until real external groups are supplied.' }
  if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'npm.cmd is unavailable; install Node.js LTS and retry.' }
  & npm.cmd run test:frontend
  if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed with exit code $LASTEXITCODE." }
  & npm.cmd run build
  if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE." }
  Write-Output 'Verification passed. External aircraft validation remains blocked pending independent data.'
}
finally {
  Pop-Location
}
