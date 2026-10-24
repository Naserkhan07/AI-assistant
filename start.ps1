# Nixi AI Desktop Assistant - Startup Script
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Magenta
Write-Host "             STARTING NIXI AI DESKTOP ASSISTANT           " -ForegroundColor Magenta
Write-Host "   (Minimal Floating Pill • Dictation • Screen Vision)    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Magenta
Write-Host ""

# Load environment variables
$envFile = if (Test-Path ".env") { ".env" } elseif (Test-Path "app\.env") { "app\.env" } else { $null }
if ($envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
        }
    }
    Write-Host "[+] Loaded environment from $envFile" -ForegroundColor Green
}

# Ensure FreeLLMAPI has keyless zero-cost providers seeded
if (Test-Path "repos\freellmapi\add-keyless-providers.mjs") {
    Push-Location "repos\freellmapi"
    node add-keyless-providers.mjs 2>$null | Out-Null
    Pop-Location
}

# Check FreeLLMAPI
Write-Host "[*] Checking FreeLLMAPI gateway on http://localhost:3001..." -ForegroundColor Yellow
$freeLlmOnline = $false

try {
    $req = [System.Net.WebRequest]::Create("http://localhost:3001/v1/models")
    $req.Timeout = 2000
    if ($env:FREELLMAPI_KEY) {
        $req.Headers.Add("Authorization", "Bearer " + $env:FREELLMAPI_KEY)
    }
    $resp = $req.GetResponse()
    $freeLlmOnline = $true
    $resp.Close()
} catch [System.Net.WebException] {
    if ($_.Response -ne $null) {
        $freeLlmOnline = $true
        $_.Response.Close()
    }
} catch {
}

if ($freeLlmOnline) {
    Write-Host "[+] FreeLLMAPI is online and ready" -ForegroundColor Green
} else {
    Write-Host "[-] FreeLLMAPI is not running. Starting in background..." -ForegroundColor Yellow
    if (Test-Path "repos\freellmapi\server\dist\index.js") {
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\repos\freellmapi'; node server/dist/index.js" -WindowStyle Minimized
        Start-Sleep -Seconds 3
        Write-Host "[+] FreeLLMAPI launched" -ForegroundColor Green
    }
}

# Resolve Virtual Environment Python
$venvPython = "$PSScriptRoot\app\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    $venvPython = "python"
}

Write-Host "[*] Booting Nixi Floating Pill Interface..." -ForegroundColor Cyan
Write-Host "[*] The floating pill will appear at the top center of your screen." -ForegroundColor White
Write-Host "[*] Shortcuts: F8 = Dictation Toggle, F9 = Chat Panel, F10 = Screen Vision" -ForegroundColor White
Write-Host ""

# Stop any older running Nixi instances to release audio devices and RAM
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*nixi\main.py*" -and $_.ProcessId -ne $PID } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

$env:QT_LOGGING_RULES = "qt.qpa.window.warning=false;qt.qpa.window=false"
& $venvPython nixi\main.py

Write-Host ""
Write-Host "Nixi session closed." -ForegroundColor Magenta
