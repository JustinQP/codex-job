param(
  [string]$ApiToken = "dev-token",
  [string]$BridgeToken = "dev-token",
  [string]$BackendHost = "127.0.0.1",
  [int]$BackendPort = 8000,
  [string]$BridgeHost = "127.0.0.1",
  [int]$BridgePort = 8766,
  [string]$CodexCommand = "codex.cmd",
  [switch]$BuildFrontend,
  [switch]$RunSmoke
)

$ErrorActionPreference = "Stop"

function Quote-ForPowerShell {
  param([string]$Value)
  return "'" + ($Value -replace "'", "''") + "'"
}

$ProjectRoot = (Get-Location).Path
$BackendMain = Join-Path $ProjectRoot "backend\main.py"
$BridgeScript = Join-Path $ProjectRoot "poc\app_server\app_server_bridge.py"
$FrontendIndex = Join-Path $ProjectRoot "frontend\dist\index.html"

if (-not (Test-Path -LiteralPath $BackendMain)) {
  Write-Error "backend/main.py not found. Please run this script from the project root."
  exit 1
}

if (-not (Test-Path -LiteralPath $BridgeScript)) {
  Write-Error "poc/app_server/app_server_bridge.py not found. Please run this script from the project root."
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
    Write-Host "npm install"
    Write-Host "npm run build"
    Write-Host ""
    Write-Host "Or rerun this script with -BuildFrontend."
    exit 1
  }
}

$BackendBaseUrl = "http://${BackendHost}:$BackendPort"
$BridgeBaseUrl = "http://${BridgeHost}:$BridgePort"

$env:API_TOKEN = $ApiToken
$env:APP_SERVER_BRIDGE_TOKEN = $BridgeToken
$env:APP_SERVER_BRIDGE_URL = $BridgeBaseUrl

$QuotedProjectRoot = Quote-ForPowerShell $ProjectRoot
$QuotedBridgeToken = Quote-ForPowerShell $BridgeToken
$QuotedApiToken = Quote-ForPowerShell $ApiToken
$QuotedBridgeUrl = Quote-ForPowerShell $BridgeBaseUrl
$QuotedBridgeHost = Quote-ForPowerShell $BridgeHost
$QuotedBackendHost = Quote-ForPowerShell $BackendHost
$QuotedCodexCommand = Quote-ForPowerShell $CodexCommand

$BridgeCommand = @"
Set-Location -LiteralPath $QuotedProjectRoot
`$env:APP_SERVER_BRIDGE_TOKEN = $QuotedBridgeToken
python .\poc\app_server\app_server_bridge.py --host $QuotedBridgeHost --port $BridgePort --codex-command $QuotedCodexCommand
"@

$BackendCommand = @"
Set-Location -LiteralPath $QuotedProjectRoot
`$env:API_TOKEN = $QuotedApiToken
`$env:APP_SERVER_BRIDGE_URL = $QuotedBridgeUrl
`$env:APP_SERVER_BRIDGE_TOKEN = $QuotedBridgeToken
python -m uvicorn backend.main:app --host $QuotedBackendHost --port $BackendPort
"@

Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BridgeCommand)
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand)

Write-Host "Started App Server Bridge sidecar: $BridgeBaseUrl"
Write-Host "Started Backend API: $BackendBaseUrl"
Write-Host ""
Write-Host "主线 mobile:"
Write-Host "$BackendBaseUrl/mobile"
Write-Host ""
Write-Host "Bridge POC mobile:"
Write-Host "$BridgeBaseUrl/mobile"
Write-Host ""
Write-Host "Smoke:"
Write-Host "python .\scripts\smoke_app_server_flow.py --base-url $BackendBaseUrl --project-path $ProjectRoot"

if ($RunSmoke) {
  Start-Sleep -Seconds 5
  python .\scripts\smoke_app_server_flow.py --base-url $BackendBaseUrl --project-path $ProjectRoot
  exit $LASTEXITCODE
}
