from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_readme_v2_overview_contains_key_sections() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "当前版本：v2.0.0" in readme
    assert "/mobile" in readme
    assert "Device Agent" in readme
    assert "python -m compileall backend agent scripts" in readme
    assert "API_TOKEN 和 AGENT_TOKEN 必须配置且不能相同" in readme
    assert "只在本机或可信局域网运行" in readme
    assert "/runs" in readme


def test_current_docs_exist() -> None:
    expected = [
        "docs/README.md",
        "docs/feature-usage.md",
        "docs/api-overview.md",
        "docs/app-server-session.md",
        "docs/state-machines.md",
        "docs/smoke-checklist.md",
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
        "feature-usage.md",
        "smoke-checklist.md",
        "state-machines.md",
    }

    actual_root_files = {path.name for path in DOCS.glob("*.md")}

    assert actual_root_files == expected_root_files


def test_active_plan_directory_is_bounded() -> None:
    active_plans = {path.name for path in (DOCS / "20-plan").glob("*.md")}

    assert active_plans == set()


def test_legacy_plans_are_discoverable_from_archive_index() -> None:
    archive = (DOCS / "90-archive" / "README.md").read_text(encoding="utf-8")

    assert "224589d6262e27700dc067681493f28e41b0a303" in archive
    assert "01-mvp-design.md" in archive
    assert "v1.0.0-plan.md" in archive
    assert "mobile-ui-ux-v1.1-plan.md" in archive
    assert "mobile-v1.7-frontend-split-plan.md" in archive
    assert "v1.9.0-plan.md" in archive
    assert "v1.8 Conversation-first" in archive
    assert "multi-device-continuous-session-roadmap.md" in archive
    assert "multi-device-continuous-session-codex-task-list.md" in archive


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


def test_smoke_checklist_documents_local_e2e_script() -> None:
    smoke = (DOCS / "smoke-checklist.md").read_text(encoding="utf-8")

    assert "python scripts\\smoke_local_e2e.py" in smoke
    assert "Control Plane" in smoke
    assert "Device Agent" in smoke
    assert "read-only Run" in smoke
    assert "Session Turn" in smoke
    assert "取消" in smoke
    assert "关闭" in smoke


def test_pytest_defaults_do_not_use_data_runtime_paths() -> None:
    pytest_ini = (ROOT / "pytest.ini").read_text(encoding="utf-8")

    assert "data/pytest-tmp-current" not in pytest_ini
    assert "data/pytest-cache" not in pytest_ini
