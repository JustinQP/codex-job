from __future__ import annotations

import argparse
import json

from agent.api_client import AgentApiClient
from agent.config import load_agent_config
from agent.heartbeat import register_agent, send_heartbeat
from agent.identity import load_or_create_identity


def main() -> None:
    parser = argparse.ArgumentParser(description="Codex Device Agent")
    parser.add_argument(
        "--print-identity",
        action="store_true",
        help="print the stable local device identity and exit",
    )
    parser.add_argument("--register", action="store_true", help="register this agent and exit")
    parser.add_argument("--heartbeat", action="store_true", help="send one heartbeat and exit")
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


if __name__ == "__main__":
    main()
