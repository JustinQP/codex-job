from __future__ import annotations

import json
import platform
import socket

from agent.api_client import AgentApiClient
from agent.identity import AgentIdentity
from backend.schemas import DeviceHeartbeat, DeviceRegister


AGENT_VERSION = "2.0.0"


def build_register_payload(identity: AgentIdentity, *, app_server_enabled: bool = False) -> DeviceRegister:
    return DeviceRegister(
        device_id=identity.device_id,
        display_name=identity.display_name,
        hostname=socket.gethostname(),
        os_name=platform.platform(),
        agent_version=AGENT_VERSION,
        capabilities_json=json.dumps(
            {
                "codex_exec": True,
                "app_server": app_server_enabled,
            },
            separators=(",", ":"),
        ),
    )


def build_heartbeat_payload(identity: AgentIdentity, *, app_server_enabled: bool = False) -> DeviceHeartbeat:
    register_payload = build_register_payload(identity, app_server_enabled=app_server_enabled)
    return DeviceHeartbeat(
        device_id=register_payload.device_id,
        display_name=register_payload.display_name,
        hostname=register_payload.hostname,
        os_name=register_payload.os_name,
        agent_version=register_payload.agent_version,
        capabilities_json=register_payload.capabilities_json,
    )


def register_agent(client: AgentApiClient, identity: AgentIdentity, *, app_server_enabled: bool = False) -> dict:
    return client.register(build_register_payload(identity, app_server_enabled=app_server_enabled))


def send_heartbeat(client: AgentApiClient, identity: AgentIdentity, *, app_server_enabled: bool = False) -> dict:
    return client.heartbeat(build_heartbeat_payload(identity, app_server_enabled=app_server_enabled))
