# PaySift Local Environment Setup (PowerShell)
# Sets up Docker sandbox, python venv, dependencies, .env, and verifies selftest.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

Write-Host "=== PaySift Local Setup ===" -ForegroundColor Cyan

# 1. Check Docker
Write-Host "`n[1/5] Checking Docker daemon..." -ForegroundColor Yellow
$dockerOk = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerOk = $true
        Write-Host "Docker is installed and running." -ForegroundColor Green
    }
} catch {
    $dockerOk = $false
}

if ($dockerOk) {
    Write-Host "Building Docker sandbox image paysift-sandbox:1..." -ForegroundColor Yellow
    docker build -t paysift-sandbox:1 -f runner/Dockerfile .
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Docker sandbox image built successfully." -ForegroundColor Green
    } else {
        Write-Warning "Docker build returned non-zero exit code. Sandbox execution may be limited."
    }
} else {
    Write-Warning "Docker is not running or not installed. Candidate sandbox execution will be unavailable."
}

# 2. Virtual Environment and dependencies
Write-Host "`n[2/5] Setting up Python virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "$ProjectRoot\.venv")) {
    python -m venv .venv
    Write-Host "Created .venv." -ForegroundColor Green
} else {
    Write-Host ".venv already exists." -ForegroundColor Green
}

$VenvPython = "$ProjectRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $VenvPython = "python"
}

Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt
Write-Host "Dependencies installed." -ForegroundColor Green

# 3. Environment configuration
Write-Host "`n[3/5] Checking .env configuration..." -ForegroundColor Yellow
if (-not (Test-Path "$ProjectRoot\.env")) {
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
    Write-Host "Copied .env.example to .env. Edit .env to add your API keys." -ForegroundColor Green
} else {
    Write-Host ".env file already exists; leaving untouched." -ForegroundColor Green
}

# 4. Self-test pipeline
Write-Host "`n[4/5] Running PaySift self-test pipeline..." -ForegroundColor Yellow
& $VenvPython cli.py selftest
$selftestCode = $LASTEXITCODE

# 5. Instructions
Write-Host "`n[5/5] Setup completed!" -ForegroundColor Cyan
Write-Host "`nTo start the PaySift backend API, run:" -ForegroundColor White
Write-Host "  python cli.py serve" -ForegroundColor Yellow
Write-Host "`nTo start the PaySift frontend UI, run:" -ForegroundColor White
Write-Host "  cd ui" -ForegroundColor Yellow
Write-Host "  npm install" -ForegroundColor Yellow
Write-Host "  npm run dev" -ForegroundColor Yellow
Write-Host ""
exit $selftestCode
