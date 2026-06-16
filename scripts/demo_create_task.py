from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


def request_json(base_url: str, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        raise

    return json.loads(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a demo Codex Runner task")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--project-id", type=int)
    parser.add_argument("--project-name", default="demo-project")
    parser.add_argument("--project-path", default=str(Path.cwd()))
    parser.add_argument(
        "--prompt",
        default="请查看 README.md，并用一句话总结这个项目当前用途。",
    )
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    project_id = args.project_id
    if project_id is None:
        project = request_json(
            args.base_url,
            "POST",
            "/projects",
            {
                "name": args.project_name,
                "path": str(Path(args.project_path).expanduser().resolve()),
                "enabled": True,
            },
        )
        project_id = int(project["id"])
        print("created project:")
        print(json.dumps(project, ensure_ascii=False, indent=2))

    task = request_json(
        args.base_url,
        "POST",
        "/tasks",
        {
            "project_id": project_id,
            "prompt": args.prompt,
            "timeout_seconds": args.timeout_seconds,
        },
    )
    print("created task:")
    print(json.dumps(task, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
