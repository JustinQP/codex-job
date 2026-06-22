from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser().resolve()


@dataclass(frozen=True)
class AgentConfig:
    data_dir: Path
    display_name: str

    @property
    def identity_path(self) -> Path:
        return self.data_dir / "identity.json"


def load_agent_config() -> AgentConfig:
    data_dir = _env_path("CODEX_AGENT_DATA_DIR", ROOT_DIR / "data" / "agent")
    display_name = os.environ.get("CODEX_AGENT_DISPLAY_NAME") or socket.gethostname()
    return AgentConfig(data_dir=data_dir, display_name=display_name.strip() or socket.gethostname())
