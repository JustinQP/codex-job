param(
    [ValidateSet("Start", "Stop", "Clean", "Prepare")]
    [string]$Action = "Start",
    [string]$BackendUrl = "http://127.0.0.1:8000",
    [string]$AgentToken = $env:AGENT_TOKEN,
    [string]$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$DataRoot = "",
    [string]$WorkspaceRoot = "",
    [switch]$Register,
    [switch]$SyncWorkspaces,
    [switch]$RunOnce
)

$ErrorActionPreference = "Stop"

if (-not $DataRoot) {
    $DataRoot = Join-Path $RootDir "data\dual-fake-agents"
}
if (-not $WorkspaceRoot) {
    $WorkspaceRoot = Join-Path $DataRoot "workspaces"
}

$PidRoot = Join-Path $DataRoot "pids"
$LogRoot = Join-Path $DataRoot "logs"

$Agents = @(
    @{
        Name = "A"
        DeviceId = "fake-agent-a"
        DisplayName = "Fake Agent A"
        DataDir = Join-Path $DataRoot "agent-a"
        WorkspaceKey = "fake-a"
        WorkspaceName = "Fake Workspace A"
        WorkspaceDir = Join-Path $WorkspaceRoot "agent-a"
    },
    @{
        Name = "B"
        DeviceId = "fake-agent-b"
        DisplayName = "Fake Agent B"
        DataDir = Join-Path $DataRoot "agent-b"
        WorkspaceKey = "fake-b"
        WorkspaceName = "Fake Workspace B"
        WorkspaceDir = Join-Path $WorkspaceRoot "agent-b"
    }
)

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Write-AgentFiles {
    param([hashtable]$Agent)

    Ensure-Directory $Agent.DataDir
    Ensure-Directory $Agent.WorkspaceDir

    $identityPath = Join-Path $Agent.DataDir "identity.json"
    if (-not (Test-Path -LiteralPath $identityPath)) {
        @{
            device_id = $Agent.DeviceId
            display_name = $Agent.DisplayName
            created_at = (Get-Date).ToUniversalTime().ToString("o")
        } | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path $identityPath
    }

    $workspaceFile = Join-Path $Agent.DataDir "workspaces.json"
    @{
        allowed_roots = @($WorkspaceRoot)
        workspaces = @(
            @{
                key = $Agent.WorkspaceKey
                name = $Agent.WorkspaceName
                path = $Agent.WorkspaceDir
                enabled = $true
            }
        )
    } | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -Path $workspaceFile
}

function Invoke-AgentOnce {
    param(
        [hashtable]$Agent,
        [string]$Argument
    )

    $env:CODEX_AGENT_DATA_DIR = $Agent.DataDir
    $env:CODEX_AGENT_DISPLAY_NAME = $Agent.DisplayName
    $env:CODEX_AGENT_WORKSPACES_FILE = Join-Path $Agent.DataDir "workspaces.json"
    $env:BACKEND_URL = $BackendUrl
    if ($AgentToken) {
        $env:AGENT_TOKEN = $AgentToken
    }
    python -m agent.main $Argument
}

function Start-AgentLoop {
    param([hashtable]$Agent)

    $envBlock = @{
        CODEX_AGENT_DATA_DIR = $Agent.DataDir
        CODEX_AGENT_DISPLAY_NAME = $Agent.DisplayName
        CODEX_AGENT_WORKSPACES_FILE = Join-Path $Agent.DataDir "workspaces.json"
        BACKEND_URL = $BackendUrl
    }
    if ($AgentToken) {
        $envBlock.AGENT_TOKEN = $AgentToken
    }

    $envScript = ($envBlock.GetEnumerator() | ForEach-Object {
        '$env:{0} = "{1}"' -f $_.Key, ($_.Value -replace '"', '\"')
    }) -join "; "
    $agentCommand = "$envScript; python -m agent.main --run-loop"
    $logPath = Join-Path $LogRoot "agent-$($Agent.Name.ToLower()).log"
    $process = Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $agentCommand) `
        -WorkingDirectory $RootDir `
        -RedirectStandardOutput $logPath `
        -RedirectStandardError $logPath `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -Encoding ASCII -Path (Join-Path $PidRoot "agent-$($Agent.Name.ToLower()).pid") -Value $process.Id
    Write-Host "Started $($Agent.DisplayName) pid=$($process.Id) log=$logPath"
}

function Stop-Agents {
    Ensure-Directory $PidRoot
    Get-ChildItem -Path $PidRoot -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
        $pidValue = (Get-Content -Path $_.FullName -Raw).Trim()
        if ($pidValue) {
            $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
            if ($process) {
                Stop-Process -Id $process.Id -Force
                Write-Host "Stopped pid=$($process.Id)"
            }
        }
        Remove-Item -LiteralPath $_.FullName -Force
    }
}

if ($Action -eq "Clean") {
    Stop-Agents
    if (Test-Path -LiteralPath $DataRoot) {
        Remove-Item -LiteralPath $DataRoot -Recurse -Force
        Write-Host "Cleaned $DataRoot"
    }
    exit 0
}

if ($Action -eq "Stop") {
    Stop-Agents
    exit 0
}

Ensure-Directory $DataRoot
Ensure-Directory $WorkspaceRoot
Ensure-Directory $PidRoot
Ensure-Directory $LogRoot
$Agents | ForEach-Object { Write-AgentFiles $_ }

if ($Action -eq "Prepare") {
    Write-Host "Prepared dual fake agents under $DataRoot"
    exit 0
}

if (-not $AgentToken) {
    Write-Host "AGENT_TOKEN is empty. Set -AgentToken or `$env:AGENT_TOKEN when the backend requires agent auth."
}

foreach ($agent in $Agents) {
    if ($Register) {
        Invoke-AgentOnce $agent "--register"
    }
    if ($SyncWorkspaces) {
        Invoke-AgentOnce $agent "--sync-workspaces"
    }
    if ($RunOnce) {
        Invoke-AgentOnce $agent "--run-once"
    } else {
        Start-AgentLoop $agent
    }
}

Write-Host "Expected backend result: two ONLINE devices fake-agent-a/fake-agent-b and two independent Workspaces."
Write-Host "Stop:  .\scripts\start_dual_fake_agents.ps1 -Action Stop"
Write-Host "Clean: .\scripts\start_dual_fake_agents.ps1 -Action Clean"
