from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_local_e2e_smoke_script_covers_mainline_flow() -> None:
    script = (ROOT / "scripts" / "smoke_local_e2e.py").read_text(encoding="utf-8")

    assert "run_local_e2e_smoke" in script
    assert "TestClient(app)" in script
    assert "AgentCommandLoop" in script
    assert "DeviceRegister" in script
    assert "WorkspaceSyncRequest" in script
    assert '"/projects"' in script
    assert '"/runs"' in script
    assert '"sandbox": "read-only"' in script
    assert '"/app-threads"' in script
    assert "/turns/async" in script
    assert "/app-turns/" in script
    assert "/cancel" in script
    assert "/app-threads/" in script
    assert "FakeJsonlRpcClient" in script
    assert "CODEX_AGENT_FAKE_RUN" in script
    assert "SMOKE PASS" in script


def test_local_e2e_smoke_script_runs_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/smoke_local_e2e.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "SMOKE PASS" in result.stdout
