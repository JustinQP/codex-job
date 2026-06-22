from __future__ import annotations

import argparse
import json

from agent.config import load_agent_config
from agent.identity import load_or_create_identity


def main() -> None:
    parser = argparse.ArgumentParser(description="Codex Device Agent")
    parser.add_argument(
        "--print-identity",
        action="store_true",
        help="print the stable local device identity and exit",
    )
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


if __name__ == "__main__":
    main()
