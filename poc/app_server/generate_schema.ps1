$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Push-Location $repoRoot
try {
    New-Item -ItemType Directory -Force -Path ".\poc\app_server\schema" | Out-Null
    codex.cmd app-server generate-json-schema --out ".\poc\app_server\schema"
}
finally {
    Pop-Location
}
