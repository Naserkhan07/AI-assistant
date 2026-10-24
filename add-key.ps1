# ══════════════════════════════════════════════════════════════════════════════
# JARVIS AI ASSISTANT — ADD FREE PROVIDER KEY HELPER
# Run: .\add-key.ps1
# ══════════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           JARVIS — FREE AI PROVIDER KEY SETUP                          ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "FreeLLMAPI routes requests across 34 free AI providers (Groq, Cerebras," -ForegroundColor White
Write-Host "Google AI Studio, Mistral, GitHub Models, etc.) at ₹0 cost." -ForegroundColor White
Write-Host ""
Write-Host "FreeLLMAPI Dashboard URL:  http://localhost:3001" -ForegroundColor Yellow
Write-Host "First-run Setup Code:     K7BJJ87FGP" -ForegroundColor Green
Write-Host ""

$choice = Read-Host "Would you like to open the FreeLLMAPI Dashboard in your browser now? (Y/N)"
if ($choice -match "^[Yy]") {
    Start-Process "http://localhost:3001"
    Write-Host "► Opened http://localhost:3001 in your default browser." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps in the dashboard:" -ForegroundColor Yellow
    Write-Host "  1. If prompted for setup code, enter: K7BJJ87FGP" -ForegroundColor White
    Write-Host "  2. Go to 'Providers' or 'Keys'" -ForegroundColor White
    Write-Host "  3. Add any free API key (e.g. Groq from https://console.groq.com/keys" -ForegroundColor White
    Write-Host "     or Gemini from https://aistudio.google.com/apikey)" -ForegroundColor White
    Write-Host "  4. Once added, launch Jarvis using: .\start.ps1" -ForegroundColor Green
} else {
    Write-Host "You can open http://localhost:3001 anytime to configure provider keys." -ForegroundColor Yellow
}
Write-Host ""
