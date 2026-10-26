$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Nixi environment is missing. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Load .env values into this process (does not spawn or open a shell window).
$envPath = Join-Path $PSScriptRoot ".env"
if (Test-Path $envPath) {
    foreach ($line in Get-Content $envPath) {
        if ($line -notmatch '^\s*#' -and $line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            $key = $Matches[1]
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

$env:QT_LOGGING_RULES = "qt.qpa.window.warning=false;qt.qpa.window=false"
Write-Host "Starting Nixi. Local built-in actions remain available if the model gateway is offline." -ForegroundColor Cyan
& $venvPython (Join-Path $PSScriptRoot "nixi\main.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Nixi exited with code $LASTEXITCODE. Run .\setup.ps1 and review diagnostics." -ForegroundColor Red
    exit $LASTEXITCODE
}
