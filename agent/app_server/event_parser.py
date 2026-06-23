from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ASSISTANT_TYPES = {
    "agentmessage",
    "agent_message",
    "assistant",
    "assistantmessage",
    "assistant_message",
}


def load_events(path: str | Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    event_path = Path(path)
    if not event_path.exists():
        return events
    with event_path.open("r", encoding="utf-8", errors="replace") as file:
        for line_number, raw_line in enumerate(file, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                events.append({"__invalid_json__": True, "line": line_number, "error": str(exc), "raw": stripped})
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
            else:
                events.append({"__non_object_json__": True, "line": line_number, "value": parsed})
    return events


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_types = [_event_type(event) for event in events]
    unknown_samples = [
        _compact_event(event)
        for event, event_type in zip(events, event_types)
        if event_type == "unknown"
    ][:5]
    assistant_text = extract_assistant_text(events)
    errors = detect_errors(events)
    return {
        "total_events": len(events),
        "event_type_counts": dict(Counter(event_types)),
        "unknown_events": len([event_type for event_type in event_types if event_type == "unknown"]),
        "unknown_event_samples": unknown_samples,
        "ids": extract_thread_or_session_ids(events),
        "assistant_text_length": len(assistant_text),
        "assistant_text_preview": assistant_text[:500],
        "has_errors": bool(errors),
        "errors": errors,
    }


def extract_assistant_text(events: list[dict[str, Any]]) -> str:
    completed_texts: list[str] = []
    final_texts: list[str] = []
    delta_by_item_id: dict[str, list[str]] = {}
    delta_without_item_id: list[str] = []
    fallback_texts: list[str] = []
    for event in events:
        event_type = _event_type(event).lower()
        containers = _event_containers(event)
        item = _first_dict_by_key(containers, "item")
        if item and _is_assistant_container(item):
            item_text = _extract_direct_text(item)
            if item_text:
                completed_texts.append(item_text)
                if _normalized(item.get("phase")) == "final_answer":
                    final_texts.append(item_text)
        if _looks_like_assistant_event(event_type):
            for container in containers:
                delta = container.get("delta")
                if isinstance(delta, str) and delta:
                    item_id = _string_or_none(container.get("itemId") or container.get("item_id"))
                    if item_id:
                        delta_by_item_id.setdefault(item_id, []).append(delta)
                    else:
                        delta_without_item_id.append(delta)
                direct_text = _extract_direct_text(container)
                if direct_text:
                    fallback_texts.append(direct_text)
        for assistant_container in _walk_assistant_containers(event):
            direct_text = _extract_direct_text(assistant_container)
            if direct_text:
                fallback_texts.append(direct_text)
    if final_texts:
        return final_texts[-1]
    if completed_texts:
        return completed_texts[-1]
    if delta_by_item_id:
        last_item_id = next(reversed(delta_by_item_id))
        return "".join(delta_by_item_id[last_item_id])
    if delta_without_item_id:
        return "".join(delta_without_item_id)
    return fallback_texts[-1] if fallback_texts else ""


def extract_thread_or_session_ids(events: list[dict[str, Any]]) -> dict[str, list[str]]:
    ids: dict[str, set[str]] = {
        "thread_ids": set(),
        "session_ids": set(),
        "turn_ids": set(),
        "item_ids": set(),
    }

    def visit(value: Any, parent_key: str | None = None) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = _normalized(key)
                if isinstance(child, str):
                    if normalized_key in {"threadid", "thread_id"}:
                        ids["thread_ids"].add(child)
                    elif normalized_key in {"sessionid", "session_id"}:
                        ids["session_ids"].add(child)
                    elif normalized_key in {"turnid", "turn_id"}:
                        ids["turn_ids"].add(child)
                    elif normalized_key in {"itemid", "item_id"}:
                        ids["item_ids"].add(child)
                if normalized_key == "id" and isinstance(child, str):
                    parent = _normalized(parent_key)
                    if parent == "thread":
                        ids["thread_ids"].add(child)
                    elif parent == "session":
                        ids["session_ids"].add(child)
                    elif parent == "turn":
                        ids["turn_ids"].add(child)
                    elif parent == "item":
                        ids["item_ids"].add(child)
                visit(child, key)
        elif isinstance(value, list):
            for child in value:
                visit(child, parent_key)

    for event in events:
        visit(event)
    return {name: sorted(values) for name, values in ids.items()}


def detect_errors(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        event_type = _event_type(event)
        error_value = _find_error_value(event)
        if error_value is not None:
            errors.append({"index": index, "event_type": event_type, "error": _compact_event(error_value)})
            continue
        lowered_type = event_type.lower()
        if event_type != "unknown" and "error" in lowered_type:
            errors.append({"index": index, "event_type": event_type, "error": _compact_event(event)})
    return errors


def write_summary(run_dir: str | Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    output_dir = Path(run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    assistant_text = extract_assistant_text(events)
    summary = summarize_events(events)
    summary["assistant_final_path"] = str(output_dir / "assistant-final.md")
    summary["summary_path"] = str(output_dir / "run-summary.json")
    (output_dir / "assistant-final.md").write_text(assistant_text, encoding="utf-8", errors="replace")
    (output_dir / "run-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
        errors="replace",
    )
    return summary


def _event_type(event: dict[str, Any]) -> str:
    if event.get("__invalid_json__"):
        return "invalid_json"
    if event.get("__non_object_json__"):
        return "non_object_json"
    for key in ("method", "type", "event"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    if "id" in event and ("result" in event or "error" in event):
        return "response"
    return "unknown"


def _event_containers(event: dict[str, Any]) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = [event]
    for key in ("params", "result", "item", "message", "delta", "content", "output"):
        value = event.get(key)
        if isinstance(value, dict):
            containers.append(value)
    params = event.get("params")
    result = event.get("result")
    for parent in (params, result):
        if isinstance(parent, dict):
            for key in ("item", "message", "delta", "content", "output"):
                value = parent.get(key)
                if isinstance(value, dict):
                    containers.append(value)
    return containers


def _first_dict_by_key(containers: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    for container in containers:
        value = container.get(key)
        if isinstance(value, dict):
            return value
    return None


def _is_assistant_container(container: dict[str, Any]) -> bool:
    role = _normalized(container.get("role"))
    item_type = _normalized(container.get("type"))
    return role == "assistant" or item_type in ASSISTANT_TYPES


def _looks_like_assistant_event(event_type: str) -> bool:
    normalized_type = _normalized(event_type)
    return "assistant" in normalized_type or "agentmessage" in normalized_type or "agent_message" in normalized_type


def _walk_assistant_containers(value: Any) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if _is_assistant_container(value):
            matches.append(value)
        for child in value.values():
            matches.extend(_walk_assistant_containers(child))
    elif isinstance(value, list):
        for child in value:
            matches.extend(_walk_assistant_containers(child))
    return matches


def _extract_direct_text(container: dict[str, Any]) -> str:
    for key in ("text", "message", "output"):
        value = container.get(key)
        text = _text_from_value(value)
        if text:
            return text
    content_text = _text_from_value(container.get("content"))
    if content_text:
        return content_text
    return ""


def _text_from_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        collected: list[str] = []
        for key in ("text", "content", "message", "output"):
            text = _text_from_value(value.get(key))
            if text:
                collected.append(text)
        return "".join(collected)
    if isinstance(value, list):
        return "".join(_text_from_value(item) for item in value)
    return ""


def _find_error_value(value: Any) -> Any:
    if isinstance(value, dict):
        for key, child in value.items():
            if _normalized(key) == "error" and child not in (None, "", [], {}):
                return child
            found = _find_error_value(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_error_value(child)
            if found is not None:
                return found
    return None


def _compact_event(value: Any, max_string_length: int = 500) -> Any:
    if isinstance(value, str):
        return value if len(value) <= max_string_length else value[:max_string_length] + "...<truncated>"
    if isinstance(value, dict):
        return {key: _compact_event(child, max_string_length) for key, child in list(value.items())[:20]}
    if isinstance(value, list):
        return [_compact_event(child, max_string_length) for child in value[:10]]
    return value


def _normalized(value: Any) -> str:
    return str(value or "").replace("-", "_").replace("/", "_").lower()


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
