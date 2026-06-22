from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_readme_v1_stable_overview_contains_key_sections() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "当前版本：v1.0.0" in readme
    assert "/mobile" in readme
    assert "smoke_app_server_flow.py" in readme
    assert "App Server sidecar" in readme
    assert "Runner/codex exec" in readme


def test_current_docs_exist() -> None:
    expected = [
        "docs/README.md",
        "docs/api-overview.md",
        "docs/app-server-session.md",
        "docs/state-machines.md",
        "docs/smoke-checklist.md",
        "docs/20-plan/multi-device-continuous-session-roadmap.md",
        "docs/20-plan/multi-device-continuous-session-codex-task-list.md",
        "docs/30-rules/ai-workflow.md",
        "docs/30-rules/docs-governance.md",
        "docs/30-rules/engineering-baseline.md",
        "docs/30-rules/testing-acceptance.md",
        "docs/90-archive/README.md",
    ]

    for relative_path in expected:
        path = ROOT / relative_path
        assert path.exists(), f"missing {relative_path}"
        assert path.read_text(encoding="utf-8").strip()


def test_docs_root_contains_only_current_entry_documents() -> None:
    expected_root_files = {
        "README.md",
        "api-overview.md",
        "app-server-session.md",
        "smoke-checklist.md",
        "state-machines.md",
    }

    actual_root_files = {path.name for path in DOCS.glob("*.md")}

    assert actual_root_files == expected_root_files


def test_active_plan_directory_is_bounded() -> None:
    active_plans = {path.name for path in (DOCS / "20-plan").glob("*.md")}

    assert active_plans == {
        "multi-device-continuous-session-roadmap.md",
        "multi-device-continuous-session-codex-task-list.md",
    }


def test_legacy_plans_are_discoverable_from_archive_index() -> None:
    archive = (DOCS / "90-archive" / "README.md").read_text(encoding="utf-8")

    assert "224589d6262e27700dc067681493f28e41b0a303" in archive
    assert "01-mvp-design.md" in archive
    assert "v1.0.0-plan.md" in archive
    assert "mobile-ui-ux-v1.1-plan.md" in archive
    assert "mobile-v1.7-frontend-split-plan.md" in archive
    assert "v1.9.0-plan.md" in archive
    assert "v1.8 Conversation-first" in archive


def test_engineering_baseline_is_not_a_copy_of_docs_governance() -> None:
    engineering = (DOCS / "30-rules" / "engineering-baseline.md").read_text(
        encoding="utf-8"
    )
    governance = (DOCS / "30-rules" / "docs-governance.md").read_text(
        encoding="utf-8"
    )

    assert engineering != governance
    assert "异步任务与进程" in engineering
    assert "计划生命周期" in governance
