from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session

from backend.models import AuditEvent


def record_event(
    session: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int,
    actor_type: str = "system",
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
    commit: bool = False,
) -> AuditEvent:
    event = AuditEvent(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        actor_type=actor_type,
        actor_id=actor_id,
        payload_json=(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if payload is not None
            else None
        ),
    )
    session.add(event)
    if commit:
        session.commit()
        session.refresh(event)
    else:
        session.flush()
    return event
