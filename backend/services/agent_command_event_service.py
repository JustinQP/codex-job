from __future__ import annotations

import json

from sqlmodel import Session, func, select

from backend.models import AgentCommand, AgentCommandEvent
from backend.schemas import AgentCommandEventsUploadRead, AgentCommandEventsUploadRequest
from backend.services.agent_command_service import AgentCommandServiceError


MAX_EVENTS_PER_BATCH = 100
MAX_EVENT_PAYLOAD_BYTES = 16 * 1024


def upload_command_events(
    session: Session,
    *,
    command_id: str,
    device_id: str,
    payload: AgentCommandEventsUploadRequest,
) -> AgentCommandEventsUploadRead:
    if len(payload.events) > MAX_EVENTS_PER_BATCH:
        raise AgentCommandServiceError(
            "too_many_command_events",
            f"at most {MAX_EVENTS_PER_BATCH} events may be uploaded at once",
        )
    command = session.get(AgentCommand, command_id)
    if command is None:
        raise AgentCommandServiceError("agent_command_not_found", "agent command not found")
    if command.device_id != device_id:
        raise AgentCommandServiceError(
            "agent_command_device_mismatch",
            "agent command does not belong to this device",
        )

    sequences = [event.sequence for event in payload.events]
    if len(sequences) != len(set(sequences)):
        raise AgentCommandServiceError(
            "duplicate_event_sequence_in_batch",
            "event sequence is duplicated in the upload batch",
        )
    if sequences != sorted(sequences):
        raise AgentCommandServiceError(
            "out_of_order_command_events",
            "event sequences must be uploaded in ascending order",
        )

    latest_sequence = latest_event_sequence(session, command_id)
    accepted_count = 0
    duplicate_count = 0
    for item in payload.events:
        payload_json = json.dumps(
            item.payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(payload_json.encode("utf-8")) > MAX_EVENT_PAYLOAD_BYTES:
            raise AgentCommandServiceError(
                "command_event_too_large",
                f"event payload must be at most {MAX_EVENT_PAYLOAD_BYTES} bytes",
            )

        existing = session.exec(
            select(AgentCommandEvent).where(
                AgentCommandEvent.command_id == command_id,
                AgentCommandEvent.sequence == item.sequence,
            )
        ).first()
        if existing is not None:
            if existing.kind == item.kind and existing.payload_json == payload_json:
                duplicate_count += 1
                latest_sequence = max(latest_sequence or 0, existing.sequence)
                continue
            raise AgentCommandServiceError(
                "command_event_sequence_conflict",
                "event sequence already exists with different content",
            )

        if latest_sequence is not None and item.sequence <= latest_sequence:
            raise AgentCommandServiceError(
                "out_of_order_command_events",
                "event sequence must be greater than latest accepted sequence",
            )
        event = AgentCommandEvent(
            command_id=command_id,
            sequence=item.sequence,
            kind=item.kind,
            payload_json=payload_json,
            created_at=item.created_at,
        )
        session.add(event)
        accepted_count += 1
        latest_sequence = item.sequence

    if accepted_count:
        session.commit()
    return AgentCommandEventsUploadRead(
        accepted_count=accepted_count,
        duplicate_count=duplicate_count,
        latest_sequence=latest_sequence,
    )


def latest_event_sequence(session: Session, command_id: str) -> int | None:
    return session.exec(
        select(func.max(AgentCommandEvent.sequence)).where(
            AgentCommandEvent.command_id == command_id
        )
    ).one()
