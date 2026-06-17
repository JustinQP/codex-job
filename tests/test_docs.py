from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_v1_stable_overview_contains_key_sections() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "当前版本：v1.0.0" in readme
    assert "/mobile" in readme
    assert "smoke_app_server_flow.py" in readme
    assert "App Server sidecar" in readme
    assert "Runner/codex exec" in readme


def test_v1_docs_exist() -> None:
    expected = [
        "docs/api-overview.md",
        "docs/app-server-session.md",
        "docs/state-machines.md",
        "docs/smoke-checklist.md",
    ]

    for relative_path in expected:
        path = ROOT / relative_path
        assert path.exists(), f"missing {relative_path}"
        assert path.read_text(encoding="utf-8").strip()
