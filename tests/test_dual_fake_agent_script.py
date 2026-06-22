from __future__ import annotations

from pathlib import Path


def test_dual_fake_agent_script_has_safe_isolated_defaults() -> None:
    script = Path("scripts/start_dual_fake_agents.ps1").read_text(encoding="utf-8")

    assert '[ValidateSet("Start", "Stop", "Clean", "Prepare")]' in script
    assert 'data\\dual-fake-agents' in script
    assert 'data\\agent' not in script
    assert 'fake-agent-a' in script
    assert 'fake-agent-b' in script
    assert 'agent-a' in script
    assert 'agent-b' in script
    assert 'CODEX_AGENT_DATA_DIR' in script
    assert 'CODEX_AGENT_WORKSPACES_FILE' in script
    assert 'CODEX_AGENT_DISPLAY_NAME' in script
    assert '--register' in script
    assert '--sync-workspaces' in script
    assert '--run-loop' in script
    assert 'Start-Process' in script
    assert '-WindowStyle Hidden' in script
    assert 'Stop-Process' in script
    assert 'Remove-Item -LiteralPath $DataRoot -Recurse -Force' in script
    assert 'two ONLINE devices fake-agent-a/fake-agent-b' in script
