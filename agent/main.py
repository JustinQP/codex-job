from __future__ import annotations

import argparse
import json

from agent.api_client import AgentApiClient
from agent.command_loop import AgentCommandLoop
from agent.config import load_agent_config
from agent.heartbeat import register_agent, send_heartbeat
from agent.identity import load_or_create_identity
from agent.local_state import AgentLocalState
from agent.workspace_registry import WorkspaceRegistry
from backend.schemas import WorkspaceSyncRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="Codex Device Agent")
    parser.add_argument(
        "--print-identity",
        action="store_true",
        help="print the stable local device identity and exit",
    )
    parser.add_argument("--register", action="store_true", help="register this agent and exit")
    parser.add_argument("--heartbeat", action="store_true", help="send one heartbeat and exit")
    parser.add_argument(
        "--sync-workspaces",
        action="store_true",
        help="sync local workspace registry to the control plane and exit",
    )
    parser.add_argument("--run-once", action="store_true", help="run one command polling iteration")
    parser.add_argument("--run-loop", action="store_true", help="run the continuous command loop")
    args = parser.parse_args()

    config = load_agent_config()
    identity = load_or_create_identity(
        config.identity_path,
        display_name=config.display_name,
    )
    if args.print_identity:
        print(
            json.dumps(
                {
                    "device_id": identity.device_id,
                    "display_name": identity.display_name,
                    "created_at": identity.created_at,
                    "identity_path": str(config.identity_path),
                },
                ensure_ascii=False,
            )
        )
    if args.register or args.heartbeat:
        client = AgentApiClient(
            base_url=config.backend_url,
            agent_token=config.agent_token,
        )
        result = register_agent(client, identity) if args.register else send_heartbeat(client, identity)
        print(json.dumps(result, ensure_ascii=False))
    if args.sync_workspaces:
        client = AgentApiClient(
            base_url=config.backend_url,
            agent_token=config.agent_token,
        )
        registry = WorkspaceRegistry.load(config.workspace_config_path)
        result = client.sync_workspaces(
            WorkspaceSyncRequest(
                device_id=identity.device_id,
                workspaces=registry.to_sync_items(),
            )
        )
        print(json.dumps(result, ensure_ascii=False))
    if args.run_once or args.run_loop:
        client = AgentApiClient(
            base_url=config.backend_url,
            agent_token=config.agent_token,
        )
        registry = None
        if config.workspace_config_path.exists():
            registry = WorkspaceRegistry.load(config.workspace_config_path)
        loop = AgentCommandLoop(
            client=client,
            identity=identity,
            local_state=AgentLocalState(config.state_path),
            workspace_registry=registry,
        )
        if args.run_once:
            loop.bootstrap()
            result = loop.run_once()
            print(json.dumps(result or {"claimed": False}, ensure_ascii=False))
        else:
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                return


if __name__ == "__main__":
    main()
