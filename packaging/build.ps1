# PyInstaller + MSIX helper
if (!(Test-Path env:FREELLMAPI_SETUP_CODE)) { Write-Host "Set `$Env:FREELLMAPI_SETUP_CODE first"; }
pyinstaller --windowed --name Nixi --add-data "nixi; nixi" --hidden-import PyQt6.sip nixi/main.py
