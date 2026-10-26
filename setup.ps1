param([switch]$InstallBrowser)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "Nixi setup" -ForegroundColor Cyan

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw "Python 3.10+ was not found. Install Python and retry." }
$version = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
$parts = $version.Split('.') | ForEach-Object { [int]$_ }
if (($parts[0] -lt 3) -or (($parts[0] -eq 3) -and ($parts[1] -lt 10))) {
    throw "Nixi requires Python 3.10+. Found $version"
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & python -m venv (Join-Path $PSScriptRoot ".venv")
}
if (-not (Test-Path $venvPython)) { throw "Could not create .venv" }

Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }
if ($InstallBrowser) {
    Write-Host "Installing Playwright Chromium for controlled browser actions..." -ForegroundColor Yellow
    & $venvPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium installation failed." }
}

if (-not (Test-Path (Join-Path $PSScriptRoot ".env")) -and (Test-Path (Join-Path $PSScriptRoot ".env.example"))) {
    Copy-Item (Join-Path $PSScriptRoot ".env.example") (Join-Path $PSScriptRoot ".env")
    Write-Host "Created .env from .env.example; add provider settings if desired." -ForegroundColor Yellow
}

Write-Host "Running setup diagnostics..." -ForegroundColor Yellow
& $venvPython -m nixi.cli doctor
if ($LASTEXITCODE -ne 0) { throw "Nixi diagnostics failed." }
Write-Host "Setup complete. Start Nixi with .\start.ps1" -ForegroundColor Green
