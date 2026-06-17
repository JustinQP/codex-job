param(
  [string]$ApiToken = "dev-token",
  [string]$BridgeToken = "dev-token",
  [string]$BackendHost = "127.0.0.1",
  [int]$BackendPort = 8000,
  [string]$BridgeHost = "127.0.0.1",
  [int]$BridgePort = 8766,
  [string]$CodexCommand = "codex.cmd",
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

if (-not (Test-Path -LiteralPath $BackendMain)) {
  Write-Error "backend/main.py not found. Please run this script from the project root."
  exit 1
}

if (-not (Test-Path -LiteralPath $BridgeScript)) {
  Write-Error "poc/app_server/app_server_bridge.py not found. Please run this script from the project root."
  exit 1
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
