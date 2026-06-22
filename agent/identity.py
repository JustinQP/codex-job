from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from backend.models import utc_now


class AgentIdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentIdentity:
    device_id: str
    display_name: str
    created_at: str


def load_or_create_identity(identity_path: Path, *, display_name: str) -> AgentIdentity:
    if identity_path.exists():
        return load_identity(identity_path)

    identity = AgentIdentity(
        device_id=str(uuid4()),
        display_name=display_name,
        created_at=utc_now().isoformat(),
    )
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    identity_path.write_text(
        json.dumps(
            {
                "device_id": identity.device_id,
                "display_name": identity.display_name,
                "created_at": identity.created_at,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return identity


def load_identity(identity_path: Path) -> AgentIdentity:
    try:
        raw = json.loads(identity_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AgentIdentityError(f"identity file not found: {identity_path}") from exc
    except json.JSONDecodeError as exc:
        raise AgentIdentityError(f"identity file is not valid JSON: {identity_path}") from exc
    except OSError as exc:
        raise AgentIdentityError(f"identity file cannot be read: {identity_path}") from exc

    if not isinstance(raw, dict):
        raise AgentIdentityError(f"identity file must contain a JSON object: {identity_path}")

    device_id = _required_string(raw, "device_id", identity_path)
    stored_display_name = _required_string(raw, "display_name", identity_path)
    created_at = _required_string(raw, "created_at", identity_path)
    try:
        datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise AgentIdentityError(
            f"identity field created_at is not an ISO datetime: {identity_path}"
        ) from exc

    return AgentIdentity(
        device_id=device_id,
        display_name=stored_display_name,
        created_at=created_at,
    )


def _required_string(raw: dict, key: str, identity_path: Path) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentIdentityError(f"identity field {key} is missing or invalid: {identity_path}")
    return value
