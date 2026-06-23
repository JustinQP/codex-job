from __future__ import annotations

import json
from pathlib import Path

from agent.app_server.event_parser import (
    detect_errors,
    extract_assistant_text,
    load_events,
    summarize_events,
    write_summary,
)


def test_load_events_reads_jsonl_and_records_diagnostics(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        "\n".join(
            [
                '{"method":"initialize"}',
                "",
                "{not-json",
                '["not", "object"]',
                '{"type":"turn/completed"}',
            ]
        ),
        encoding="utf-8",
    )

    events = load_events(events_path)

    assert len(events) == 4
    assert events[0]["method"] == "initialize"
    assert events[1]["__invalid_json__"] is True
    assert events[2]["__non_object_json__"] is True
    assert events[3]["type"] == "turn/completed"


def test_summarize_events_counts_types_errors_and_assistant_preview() -> None:
    events = [
        {"method": "thread/start"},
        {"type": "turn/completed"},
        {"event": "agent/message_delta", "params": {"delta": "hello"}},
        {"id": "request-1", "result": {"ok": True}},
        {"unexpected": True},
        {"id": "request-2", "error": {"code": -1, "message": "bad"}},
    ]

    summary = summarize_events(events)

    assert summary["total_events"] == 6
    assert summary["event_type_counts"]["thread/start"] == 1
    assert summary["event_type_counts"]["turn/completed"] == 1
    assert summary["event_type_counts"]["agent/message_delta"] == 1
    assert summary["event_type_counts"]["response"] == 2
    assert summary["unknown_events"] == 1
    assert summary["has_errors"] is True
    assert summary["assistant_text_length"] == len("hello")
    assert summary["assistant_text_preview"] == "hello"


def test_extract_assistant_text_from_messages_deltas_and_nested_content() -> None:
    message_events = [
        {
            "method": "item/completed",
            "params": {
                "item": {
                    "type": "assistant_message",
                    "content": [{"text": "final answer"}],
                }
            },
        }
    ]
    delta_events = [
        {"method": "agent/message_delta", "params": {"itemId": "a", "delta": "hel"}},
        {"method": "agent/message_delta", "params": {"itemId": "a", "delta": "lo"}},
    ]
    nested_events = [
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "output": {"content": [{"text": "nested"}, {"text": " text"}]},
            },
        }
    ]

    assert extract_assistant_text(message_events) == "final answer"
    assert extract_assistant_text(delta_events) == "hello"
    assert extract_assistant_text(nested_events) == "nested text"
    assert extract_assistant_text([{"method": "turn/completed"}]) == ""


def test_detect_errors_finds_json_rpc_and_nested_errors() -> None:
    errors = detect_errors(
        [
            {"id": "1", "error": {"message": "rpc failed"}},
            {"method": "x", "params": {"error": "param failed"}},
            {"method": "y", "result": {"nested": {"error": {"message": "result failed"}}}},
            {"method": "turn/completed", "params": {"ok": True}},
        ]
    )

    assert [error["event_type"] for error in errors] == ["response", "x", "y"]
    assert detect_errors([{"method": "turn/completed"}]) == []


def test_write_summary_writes_summary_and_assistant_final(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    events = [
        {"method": "turn/start"},
        {"method": "agent/message_delta", "params": {"delta": "done"}},
    ]

    summary = write_summary(run_dir, events)

    assert (run_dir / "run-summary.json").exists()
    assert (run_dir / "assistant-final.md").read_text(encoding="utf-8") == "done"
    saved = json.loads((run_dir / "run-summary.json").read_text(encoding="utf-8"))
    assert summary["total_events"] == 2
    assert saved["total_events"] == 2
    assert saved["event_type_counts"]["turn/start"] == 1
    assert saved["has_errors"] is False
