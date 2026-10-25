# ══════════════════════════════════════════════════════════════════════════════
# NIXI AI DESKTOP ASSISTANT — MASTER SETUP SCRIPT
# Run: .\setup.ps1 from PowerShell in project root
# ══════════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              NIXI AI DESKTOP ASSISTANT — MASTER SETUP                  ║" -ForegroundColor Cyan
Write-Host "║   (Minimal Floating Pill • Streaming Voice • Screen Vision Agent)      ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check Python ───────────────────────────────────────────────────────────
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
try {
    $pyver = python --version 2>&1
    Write-Host "  Found: $pyver" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found. Please install Python 3.10+." -ForegroundColor Red
    exit 1
}

# ── 2. Check Node.js & npm (for FreeLLMAPI) ──────────────────────────────────
Write-Host "[2/5] Checking Node.js (for FreeLLMAPI gateway)..." -ForegroundColor Yellow
try {
    $nodever = node --version 2>&1
    $npmver = npm --version 2>&1
    Write-Host "  Found Node: $nodever, npm: $npmver" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: Node.js or npm not found. FreeLLMAPI gateway requires Node 18+." -ForegroundColor Yellow
}

# ── 3. Virtual Environment ───────────────────────────────────────────────────
Write-Host "[3/5] Setting up Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "app\.venv")) {
    python -m venv app\.venv
    Write-Host "  Created app\.venv" -ForegroundColor Green
} else {
    Write-Host "  app\.venv exists ✓" -ForegroundColor Green
}

$venvPython = "$PSScriptRoot\app\.venv\Scripts\python.exe"
$venvPip    = "$PSScriptRoot\app\.venv\Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "  ERROR: venv python not found at $venvPython" -ForegroundColor Red
    exit 1
}

# ── 4. Install Dependencies ──────────────────────────────────────────────────
Write-Host "[4/5] Installing Python dependencies into virtual environment..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --quiet
Write-Host "  Pip upgraded ✓" -ForegroundColor Green

if (Test-Path "requirements.txt") {
    Write-Host "  Installing dependencies from requirements.txt..." -ForegroundColor Yellow
    & $venvPip install -r requirements.txt --quiet
    Write-Host "  Nixi requirements installed ✓" -ForegroundColor Green
}

# ── 5. Environment & FreeLLMAPI Setup ────────────────────────────────────────
Write-Host "[5/5] Configuring environment & FreeLLMAPI..." -ForegroundColor Yellow

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  Created .env from .env.example ✓" -ForegroundColor Green
}

if (Test-Path "repos\freellmapi") {
    if (-not (Test-Path "repos\freellmapi\node_modules")) {
        Write-Host "  Installing FreeLLMAPI node_modules..." -ForegroundColor Yellow
        Push-Location "repos\freellmapi"
        try {
            npm install --no-audit --no-fund
            Write-Host "  FreeLLMAPI dependencies installed ✓" -ForegroundColor Green
        } catch {
            Write-Host "  Note: Run 'npm install' inside repos/freellmapi if needed." -ForegroundColor Yellow
        }
        Pop-Location
    } else {
        Write-Host "  FreeLLMAPI dependencies present ✓" -ForegroundColor Green
    }

    # Seed keyless zero-cost providers
    if (Test-Path "scripts\add-keyless-providers.mjs") {
        Push-Location "repos\freellmapi"
        node add-keyless-providers.mjs 2>$null | Out-Null
        Pop-Location
        Write-Host "  Keyless providers seeded ✓" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  NIXI SETUP COMPLETE!                                                  ║" -ForegroundColor Green
Write-Host "║                                                                        ║" -ForegroundColor Green
Write-Host "║  To launch Nixi Assistant:                                             ║" -ForegroundColor Green
Write-Host "║    .\start.ps1                                                         ║" -ForegroundColor Green
Write-Host "║                                                                        ║" -ForegroundColor Green
Write-Host "║  Shortcuts:                                                            ║" -ForegroundColor Green
Write-Host "║    F8  = Dictation Toggle (Speech-to-Text directly into focused app)   ║" -ForegroundColor Green
Write-Host "║    F9  = Expand/Collapse Dynamic Island Chat Drawer                    ║" -ForegroundColor Green
Write-Host "║    F10 = Screen Vision (Analyze screenshot via Vision AI)              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
