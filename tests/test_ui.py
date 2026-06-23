from __future__ import annotations

from pathlib import Path


FRONTEND_SRC = Path("frontend/src")


def test_frontend_uses_run_api_and_types() -> None:
    assert (FRONTEND_SRC / "api" / "runs.ts").exists()
    assert not (FRONTEND_SRC / "api" / "tasks.ts").exists()
    assert not (FRONTEND_SRC / "api" / "runners.ts").exists()

    types = (FRONTEND_SRC / "api" / "types.ts").read_text(encoding="utf-8")
    assert "export type Run" in types
    assert "export type Task" not in types
    assert "BridgeHealth" not in types
    assert "default_runner_id" not in types


def test_frontend_does_not_call_legacy_routes() -> None:
    checked = []
    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        text = path.read_text(encoding="utf-8")
        checked.append(text)
    source = "\n".join(checked)
    assert '"/tasks' not in source
    assert '"/runners' not in source
    assert '"/runner' not in source
    assert "app-server-bridge" not in source
    assert "Bridge" not in source
    assert "Runner" not in source
