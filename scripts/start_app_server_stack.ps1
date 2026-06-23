param(
  [string]$ApiToken = "dev-token",
  [string]$BackendHost = "127.0.0.1",
  [int]$BackendPort = 8000,
  [switch]$BuildFrontend
)

$ErrorActionPreference = "Stop"

function Quote-ForPowerShell {
  param([string]$Value)
  return "'" + ($Value -replace "'", "''") + "'"
}

$ProjectRoot = (Get-Location).Path
$BackendMain = Join-Path $ProjectRoot "backend\main.py"
$FrontendIndex = Join-Path $ProjectRoot "frontend\dist\index.html"

if (-not (Test-Path -LiteralPath $BackendMain)) {
  Write-Error "backend/main.py not found. Please run this script from the project root."
  exit 1
}

if (-not (Test-Path -LiteralPath $FrontendIndex)) {
  if ($BuildFrontend) {
    Write-Host "frontend/dist/index.html not found. Building frontend..."
    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
      npm.cmd install
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
      npm.cmd run build
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
      Pop-Location
    }
  } else {
    Write-Host "frontend/dist/index.html not found. Build the mobile frontend first:"
    Write-Host "cd frontend"
    Write-Host "npm.cmd install"
    Write-Host "npm.cmd run build"
    Write-Host ""
    Write-Host "Or rerun this script with -BuildFrontend."
    exit 1
  }
}

$BackendBaseUrl = "http://${BackendHost}:$BackendPort"
$env:API_TOKEN = $ApiToken

$QuotedProjectRoot = Quote-ForPowerShell $ProjectRoot
$QuotedApiToken = Quote-ForPowerShell $ApiToken
$QuotedBackendHost = Quote-ForPowerShell $BackendHost

$BackendCommand = @"
Set-Location -LiteralPath $QuotedProjectRoot
`$env:API_TOKEN = $QuotedApiToken
python -m uvicorn backend.main:app --host $QuotedBackendHost --port $BackendPort
"@

Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand)

Write-Host "Started Control Plane: $BackendBaseUrl"
Write-Host ""
Write-Host "Mobile:"
Write-Host "$BackendBaseUrl/mobile"
Write-Host ""
Write-Host "Health:"
Write-Host "Invoke-RestMethod $BackendBaseUrl/health"
