from __future__ import annotations

from pathlib import Path


def test_windows_agent_install_script_covers_install_contract() -> None:
    script = Path("scripts/install_windows_agent.ps1").read_text(encoding="utf-8")

    assert '[ValidateSet("Install", "Uninstall", "Check", "Status", "Logs")]' in script
    assert 'Assert-Command "python"' in script
    assert 'Assert-Command "codex"' in script
    assert 'Assert-Command "schtasks.exe"' in script
    assert 'Invoke-WebRequest' in script
    assert '/health' in script
    assert '$env:BACKEND_URL' in script
    assert '$env:AGENT_TOKEN' in script
    assert '$env:CODEX_AGENT_DISPLAY_NAME' in script
    assert 'CODEX_AGENT_DATA_DIR' in script
    assert 'CODEX_AGENT_WORKSPACES_FILE' in script
    assert 'workspaces.json' in script
    assert 'data\\agent' in script
    assert 'run-agent.ps1' in script
    assert '--register' in script
    assert '--sync-workspaces' in script
    assert '--run-loop' in script
    assert 'schtasks.exe /Query /TN $TaskName' in script
    assert 'already exists. Use -Force to replace it.' in script
    assert 'schtasks.exe /Create /TN $TaskName /SC ONLOGON' in script
    assert 'schtasks.exe /Delete /TN $TaskName /F' in script
    assert '*>> `$logPath' in script
    assert '"Logs" { Show-Logs }' in script
    assert 'Workspace config, and project files were not deleted' in script
    assert 'Remove-Item -LiteralPath $DataDir' not in script
    assert 'Remove-Item -LiteralPath $WorkspaceConfig' not in script
