param(
    [switch]$SkipOllama,
    [switch]$SkipObscura,
    [switch]$SkipJevSocial,
    [string]$Model = "qwen2.5:3b"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($env:OS -ne "Windows_NT") { throw "This integration installer targets Windows 10/11." }
if ($Model -notmatch '^[A-Za-z0-9._:-]{1,100}$') { throw "Invalid Ollama model name." }

$installRoot = Join-Path $env:LOCALAPPDATA "Nixi\integrations"
$binDir = Join-Path $installRoot "bin"
New-Item -ItemType Directory -Force -Path $installRoot, $binDir | Out-Null

function Get-Executable([string]$Name, [string[]]$FallbackPaths = @()) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($path in $FallbackPaths) {
        if ($path -and (Test-Path $path)) { return $path }
    }
    return $null
}

function Download-Verified([string]$Url, [string]$Destination, [string]$Sha256) {
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
    $actual = (Get-FileHash -Path $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Sha256.ToLowerInvariant()) {
        Remove-Item -Force $Destination -ErrorAction SilentlyContinue
        throw "SHA-256 verification failed for $([IO.Path]::GetFileName($Destination))."
    }
}

function Set-EnvValue([string]$Key, [string]$Value) {
    $envFile = Join-Path $PSScriptRoot ".env"
    if (-not (Test-Path $envFile) -and (Test-Path (Join-Path $PSScriptRoot ".env.example"))) {
        Copy-Item (Join-Path $PSScriptRoot ".env.example") $envFile
    }
    $lines = if (Test-Path $envFile) { @(Get-Content $envFile) } else { @() }
    $escaped = [Regex]::Escape($Key)
    $found = $false
    $updated = foreach ($line in $lines) {
        if ($line -match "^\s*$escaped\s*=") {
            $found = $true
            "$Key=`"$Value`""
        } else { $line }
    }
    if (-not $found) { $updated += "$Key=`"$Value`"" }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($envFile, [string[]]$updated, $utf8NoBom)
}

function Install-OllamaModel {
    $ollamaPaths = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
        (Join-Path $env:ProgramFiles "Ollama\ollama.exe")
    )
    $ollama = Get-Executable "ollama.exe" $ollamaPaths
    if (-not $ollama) {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if (-not $winget) { throw "Ollama is missing and winget is unavailable. Install Ollama from its official Windows installer, then rerun this script." }
        Write-Host "Installing Ollama with winget..." -ForegroundColor Yellow
        & $winget.Source install --exact --id Ollama.Ollama --source winget --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw "Ollama installation failed (exit $LASTEXITCODE)." }
        $ollama = Get-Executable "ollama.exe" $ollamaPaths
    }
    if (-not $ollama) { throw "Ollama was installed but its executable was not found. Restart PowerShell and rerun setup." }

    try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null }
    catch {
        Write-Host "Starting the local Ollama service..." -ForegroundColor Yellow
        Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
        $ready = $false
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Milliseconds 500
            try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null; $ready = $true; break } catch {}
        }
        if (-not $ready) { throw "Ollama did not start on 127.0.0.1:11434." }
    }

    Write-Host "Downloading local model $Model (first download may be several GB)..." -ForegroundColor Yellow
    & $ollama pull $Model
    if ($LASTEXITCODE -ne 0) { throw "Could not download Ollama model '$Model'." }
    $probe = @{ model = $Model; prompt = "Reply with exactly: Nixi local model ready"; stream = $false } | ConvertTo-Json -Compress
    $reply = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/generate" -Method Post -ContentType "application/json" -Body $probe -TimeoutSec 180
    if (-not $reply.response) { throw "Ollama model probe returned no response." }
    Set-EnvValue "OLLAMA_MODEL" $Model
    Write-Host "Ollama model responded: $($reply.response.Trim())" -ForegroundColor Green
}

function Install-Obscura {
    $version = "v0.2.5"
    $asset = "obscura-x86_64-windows.zip"
    $sha = "9e56fa1cc1f9e4fb78926f7e9f36c40166b65177541ad7b7fd9645944c49174e"
    $url = "https://github.com/h4ckf0r0day/obscura/releases/download/$version/$asset"
    $archive = Join-Path $env:TEMP $asset
    $stage = Join-Path $env:TEMP "nixi-obscura-stage"
    $dest = Join-Path $installRoot "obscura"
    Write-Host "Downloading Obscura $version..." -ForegroundColor Yellow
    Download-Verified $url $archive $sha
    Remove-Item -Recurse -Force $stage, $dest -ErrorAction SilentlyContinue
    Expand-Archive -Path $archive -DestinationPath $stage -Force
    $exe = Get-ChildItem -Path $stage -Filter "obscura.exe" -Recurse | Select-Object -First 1
    if (-not $exe) { throw "Verified Obscura archive did not contain obscura.exe." }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item -Path (Join-Path $exe.Directory.FullName "*") -Destination $dest -Recurse -Force
    $installed = Join-Path $dest "obscura.exe"
    if (-not (Test-Path $installed)) { throw "Obscura extraction failed." }
    & $installed --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Obscura executable smoke test failed." }
    Set-EnvValue "NIXI_OBSCURA_BIN" $installed
    Remove-Item -Force $archive -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
    Write-Host "Obscura installed and version check passed." -ForegroundColor Green
}

function Install-JevSocial {
    $nodePaths = @(
        (Join-Path $env:ProgramFiles "nodejs\node.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\nodejs\node.exe")
    )
    $npmPaths = @(
        (Join-Path $env:ProgramFiles "nodejs\npm.cmd"),
        (Join-Path $env:LOCALAPPDATA "Programs\nodejs\npm.cmd")
    )
    $node = Get-Executable "node.exe" $nodePaths
    $npm = Get-Executable "npm.cmd" $npmPaths
    if (-not $node) {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if (-not $winget) { throw "Node.js 22+ is missing and winget is unavailable. Install Node.js 22+ then rerun setup." }
        Write-Host "Installing Node.js LTS for Jev Social..." -ForegroundColor Yellow
        & $winget.Source install --exact --id OpenJS.NodeJS.LTS --source winget --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw "Node.js installation failed (exit $LASTEXITCODE)." }
        $node = Get-Executable "node.exe" $nodePaths
        $npm = Get-Executable "npm.cmd" $npmPaths
    }
    if (-not $node -or -not $npm) { throw "Node.js or npm was not found after installation. Restart PowerShell and rerun setup." }
    $nodeVersionText = & $node --version
    if ($LASTEXITCODE -ne 0 -or $nodeVersionText -notmatch '^v?(\d+)') {
        throw "Could not determine the installed Node.js version."
    }
    if ([int]$Matches[1] -lt 22) {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if (-not $winget) { throw "Jev Social requires Node.js 22+. Upgrade Node.js and rerun setup." }
        Write-Host "Upgrading Node.js to the supported LTS version..." -ForegroundColor Yellow
        & $winget.Source install --exact --id OpenJS.NodeJS.LTS --source winget --silent --force --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw "Node.js 22+ installation failed (exit $LASTEXITCODE)." }
        $node = $nodePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        $npm = $npmPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not $node) { $node = Get-Executable "node.exe" $nodePaths }
        if (-not $npm) { $npm = Get-Executable "npm.cmd" $npmPaths }
        if (-not $node -or -not $npm) { throw "Node.js 22+ was installed; restart PowerShell and rerun setup." }
        $nodeVersionText = & $node --version
        if ($LASTEXITCODE -ne 0 -or $nodeVersionText -notmatch '^v?(\d+)' -or [int]$Matches[1] -lt 22) {
            throw "Jev Social requires Node.js 22 or newer. Found $nodeVersionText."
        }
    }

    $socaiVersion = "v0.6.9"
    $socaiAsset = "socai-cli-windows-x86_64.zip"
    $socaiSha = "7888be9762304ab9b7865f2267e4548376fa6c41f3e6b08c3cb6242d2e034b01"
    $socaiUrl = "https://github.com/socai-io/socai/releases/download/$socaiVersion/$socaiAsset"
    $socaiArchive = Join-Path $env:TEMP $socaiAsset
    $socaiStage = Join-Path $env:TEMP "nixi-socai-stage"
    Download-Verified $socaiUrl $socaiArchive $socaiSha
    Remove-Item -Recurse -Force $socaiStage -ErrorAction SilentlyContinue
    Expand-Archive -Path $socaiArchive -DestinationPath $socaiStage -Force
    $socaiExe = Get-ChildItem -Path $socaiStage -Filter "socai.exe" -Recurse | Select-Object -First 1
    if (-not $socaiExe) { throw "Verified socai archive did not contain socai.exe." }
    Copy-Item -Path (Join-Path $socaiExe.Directory.FullName "*") -Destination $binDir -Recurse -Force
    $socaiDest = Join-Path $binDir "socai.exe"
    & $socaiDest --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "socai CLI smoke test failed." }

    $jevRoot = Join-Path $installRoot "jev-social"
    New-Item -ItemType Directory -Force -Path $jevRoot | Out-Null
    $jevCommit = "2f02e6f4c60943e679993634ad1017b0c97efff5"
    Write-Host "Installing Jev Social at pinned commit $jevCommit..." -ForegroundColor Yellow
    & $npm install --prefix $jevRoot --no-audit --no-fund --ignore-scripts "github:socai-io/jev-social#$jevCommit"
    if ($LASTEXITCODE -ne 0) { throw "Jev Social npm installation failed." }
    $entry = Join-Path $jevRoot "node_modules\jev-social\bin\jev-social.js"
    if (-not (Test-Path $entry)) { throw "Jev Social CLI entrypoint was not installed." }
    $jevVersion = & $node $entry --version
    if ($LASTEXITCODE -ne 0 -or $jevVersion -ne "0.1.13") { throw "Unexpected Jev Social version: $jevVersion" }

    Set-EnvValue "NIXI_SOCAI_BIN" $socaiDest
    Set-EnvValue "NIXI_JEV_SOCIAL_ENTRYPOINT" $entry
    Set-EnvValue "SOCAI_TELEMETRY" "0"
    Remove-Item -Force $socaiArchive -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $socaiStage -ErrorAction SilentlyContinue
    Write-Host "Jev Social v$jevVersion and socai CLI installed; decisions will use local Ollama." -ForegroundColor Green
}

if (-not $SkipOllama) { Install-OllamaModel }
if (-not $SkipObscura) { Install-Obscura }
if (-not $SkipJevSocial) { Install-JevSocial }

Write-Host "Integration setup complete. Restart Nixi. Cloud calls fall back to the configured local Ollama model." -ForegroundColor Green
Write-Host "Jev Social is read-only social research; it requires logged-in browser access where a platform requires it." -ForegroundColor Cyan
