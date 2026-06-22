from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from backend.models import AgentCommand, AppTurn, TurnEvent
from backend.schemas import TurnEventListRead, TurnEventRead
from backend.services.agent_command_service import AgentCommandServiceError


def record_turn_event(
    session: Session,
    *,
    turn_id: int,
    sequence: int,
    kind: str,
    payload: dict[str, Any],
    created_at,
) -> tuple[TurnEvent, bool]:
    app_turn = session.get(AppTurn, turn_id)
    if app_turn is None:
        raise AgentCommandServiceError("app_turn_not_found", "app turn not found")
    payload_json = _canonical_payload(payload)
    existing = session.exec(
        select(TurnEvent).where(
            TurnEvent.turn_id == turn_id,
            TurnEvent.sequence == sequence,
        )
    ).first()
    if existing is not None:
        if existing.kind == kind and existing.payload_json == payload_json:
            return existing, False
        raise AgentCommandServiceError(
            "turn_event_sequence_conflict",
            "turn event sequence already exists with different content",
        )

    event = TurnEvent(
        turn_id=turn_id,
        sequence=sequence,
        kind=kind,
        payload_json=payload_json,
        created_at=created_at,
    )
    session.add(event)
    return event, True


def record_from_command_event(
    session: Session,
    *,
    command: AgentCommand,
    sequence: int,
    kind: str,
    payload: dict[str, Any],
    created_at,
) -> tuple[TurnEvent, bool] | None:
    if command.command_type != "TURN_START" or command.aggregate_type != "app_turn":
        return None
    try:
        turn_id = int(command.aggregate_id or "0")
    except ValueError:
        return None
    turn_payload = _turn_payload(command, payload)
    return record_turn_event(
        session,
        turn_id=turn_id,
        sequence=sequence,
        kind=kind,
        payload=turn_payload,
        created_at=created_at,
    )


def list_turn_events(
    session: Session,
    *,
    turn_id: int,
    since: int = 0,
    limit: int = 100,
) -> TurnEventListRead:
    app_turn = session.get(AppTurn, turn_id)
    if app_turn is None:
        raise ValueError("app turn not found")
    bounded_limit = max(1, min(limit, 500))
    events = list(
        session.exec(
            select(TurnEvent)
            .where(
                TurnEvent.turn_id == turn_id,
                TurnEvent.sequence > since,
            )
            .order_by(TurnEvent.sequence)
            .limit(bounded_limit + 1)
        ).all()
    )
    has_more = len(events) > bounded_limit
    visible = events[:bounded_limit]
    next_sequence = visible[-1].sequence if has_more and visible else None
    return TurnEventListRead(
        turn_id=turn_id,
        events=[to_turn_event_read(event) for event in visible],
        next_sequence=next_sequence,
    )


def list_turn_event_models(
    session: Session,
    *,
    turn_id: int,
    since: int = 0,
    limit: int = 100,
) -> list[TurnEvent]:
    bounded_limit = max(1, min(limit, 500))
    return list(
        session.exec(
            select(TurnEvent)
            .where(
                TurnEvent.turn_id == turn_id,
                TurnEvent.sequence > since,
            )
            .order_by(TurnEvent.sequence)
            .limit(bounded_limit)
        ).all()
    )


def to_turn_event_read(event: TurnEvent) -> TurnEventRead:
    if event.id is None:
        raise ValueError("turn event id is required")
    return TurnEventRead(
        id=event.id,
        turn_id=event.turn_id,
        sequence=event.sequence,
        kind=event.kind,
        payload=_payload_from_json(event.payload_json),
        created_at=event.created_at,
    )


def _turn_payload(command: AgentCommand, payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.setdefault("command_id", command.id)
    result.setdefault("command_type", command.command_type)
    return result


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _payload_from_json(raw_value: str) -> dict[str, Any]:
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return {"invalid_payload": raw_value}
    return value if isinstance(value, dict) else {"payload": value}
