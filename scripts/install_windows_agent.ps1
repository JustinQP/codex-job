param(
    [ValidateSet("Install", "Uninstall", "Check", "Status", "Logs")]
    [string]$Action = "Install",
    [string]$TaskName = "CodexDeviceAgent",
    [string]$BackendUrl = $env:BACKEND_URL,
    [string]$AgentToken = $env:AGENT_TOKEN,
    [string]$DataDir = "",
    [string]$WorkspaceConfig = "",
    [string]$DisplayName = $env:CODEX_AGENT_DISPLAY_NAME,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $DataDir) {
    $DataDir = Join-Path $RootDir "data\agent"
}
if (-not $WorkspaceConfig) {
    $WorkspaceConfig = Join-Path $DataDir "workspaces.json"
}
if (-not $DisplayName) {
    $DisplayName = $env:COMPUTERNAME
}
$LogDir = Join-Path $DataDir "logs"
$AgentLaunchScript = Join-Path $DataDir "run-agent.ps1"

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Assert-Command {
    param([string]$Name, [string]$Hint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name not found. $Hint"
    }
}

function Test-Backend {
    if (-not $BackendUrl) {
        throw "BACKEND_URL is required. Pass -BackendUrl or set `$env:BACKEND_URL."
    }
    try {
        $response = Invoke-WebRequest -Uri ($BackendUrl.TrimEnd("/") + "/health") -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 500) {
            throw "backend health returned HTTP $($response.StatusCode)"
        }
    } catch {
        throw "Backend health check failed: $($_.Exception.Message)"
    }
}

function Invoke-EnvironmentCheck {
    Assert-Command "python" "Install Python and make sure python.exe is on PATH."
    Assert-Command "codex" "Install Codex CLI or make sure codex/codex.cmd is on PATH."
    Assert-Command "schtasks.exe" "Windows Task Scheduler CLI is required."
    if (-not $AgentToken) {
        throw "AGENT_TOKEN is required. Pass -AgentToken or set `$env:AGENT_TOKEN."
    }
    if (-not (Test-Path -LiteralPath $WorkspaceConfig)) {
        throw "Workspace config not found: $WorkspaceConfig"
    }
    Test-Backend
    Write-Host "Environment check passed."
}

function Write-AgentLaunchScript {
    Ensure-Directory $DataDir
    Ensure-Directory $LogDir
    $escapedRoot = $RootDir -replace "'", "''"
    $escapedData = $DataDir -replace "'", "''"
    $escapedWorkspaceConfig = $WorkspaceConfig -replace "'", "''"
    $escapedBackend = $BackendUrl -replace "'", "''"
    $escapedDisplayName = $DisplayName -replace "'", "''"
    $escapedToken = $AgentToken -replace "'", "''"
    $escapedLogDir = $LogDir -replace "'", "''"
    @"
`$ErrorActionPreference = "Stop"
Set-Location '$escapedRoot'
`$env:CODEX_AGENT_DATA_DIR = '$escapedData'
`$env:CODEX_AGENT_WORKSPACES_FILE = '$escapedWorkspaceConfig'
`$env:CODEX_AGENT_DISPLAY_NAME = '$escapedDisplayName'
`$env:BACKEND_URL = '$escapedBackend'
`$env:AGENT_TOKEN = '$escapedToken'
`$logDir = '$escapedLogDir'
if (-not (Test-Path -LiteralPath `$logDir)) {
    New-Item -ItemType Directory -Path `$logDir | Out-Null
}
`$logPath = Join-Path `$logDir ("agent-" + (Get-Date -Format "yyyyMMdd") + ".log")
python -m agent.main --register *>> `$logPath
python -m agent.main --sync-workspaces *>> `$logPath
python -m agent.main --run-loop *>> `$logPath
"@ | Set-Content -Encoding UTF8 -Path $AgentLaunchScript
}

function Install-AgentTask {
    Invoke-EnvironmentCheck
    Write-AgentLaunchScript
    $existing = schtasks.exe /Query /TN $TaskName 2>$null
    if ($LASTEXITCODE -eq 0 -and -not $Force) {
        Write-Host "Task '$TaskName' already exists. Use -Force to replace it."
        return
    }
    if ($LASTEXITCODE -eq 0) {
        schtasks.exe /Delete /TN $TaskName /F | Out-Null
    }
    $action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$AgentLaunchScript`""
    schtasks.exe /Create /TN $TaskName /SC ONLOGON /RL LIMITED /F /TR $action | Out-Null
    Write-Host "Installed Windows scheduled task '$TaskName'."
    Write-Host "Data dir: $DataDir"
    Write-Host "Logs: $LogDir"
}

function Uninstall-AgentTask {
    $existing = schtasks.exe /Query /TN $TaskName 2>$null
    if ($LASTEXITCODE -eq 0) {
        schtasks.exe /Delete /TN $TaskName /F | Out-Null
        Write-Host "Removed Windows scheduled task '$TaskName'."
    } else {
        Write-Host "Task '$TaskName' does not exist."
    }
    Write-Host "User data, identity, Workspace config, and project files were not deleted."
}

function Show-Status {
    schtasks.exe /Query /TN $TaskName /V /FO LIST
}

function Show-Logs {
    Ensure-Directory $LogDir
    Get-ChildItem -LiteralPath $LogDir -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 10
}

switch ($Action) {
    "Check" { Invoke-EnvironmentCheck }
    "Install" { Install-AgentTask }
    "Uninstall" { Uninstall-AgentTask }
    "Status" { Show-Status }
    "Logs" { Show-Logs }
}
