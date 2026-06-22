from __future__ import annotations

import json
import platform
import socket

from agent.api_client import AgentApiClient
from agent.identity import AgentIdentity
from backend.schemas import DeviceHeartbeat, DeviceRegister


AGENT_VERSION = "0.1.0"


def build_register_payload(identity: AgentIdentity) -> DeviceRegister:
    return DeviceRegister(
        device_id=identity.device_id,
        display_name=identity.display_name,
        hostname=socket.gethostname(),
        os_name=platform.platform(),
        agent_version=AGENT_VERSION,
        capabilities_json=json.dumps(
            {
                "codex_exec": True,
                "app_server": False,
            },
            separators=(",", ":"),
        ),
    )


def build_heartbeat_payload(identity: AgentIdentity) -> DeviceHeartbeat:
    register_payload = build_register_payload(identity)
    return DeviceHeartbeat(
        device_id=register_payload.device_id,
        display_name=register_payload.display_name,
        hostname=register_payload.hostname,
        os_name=register_payload.os_name,
        agent_version=register_payload.agent_version,
        capabilities_json=register_payload.capabilities_json,
    )


def register_agent(client: AgentApiClient, identity: AgentIdentity) -> dict:
    return client.register(build_register_payload(identity))


def send_heartbeat(client: AgentApiClient, identity: AgentIdentity) -> dict:
    return client.heartbeat(build_heartbeat_payload(identity))
