from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

FRONTEND_INDEX_HTML = Path("missing-frontend-dist-index.html")

router = APIRouter()


def frontend_build_missing_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Frontend build not found</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #f3f5f8;
      color: #172033;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(92vw, 680px);
      padding: 24px;
      border: 1px solid #d8dee8;
      border-radius: 14px;
      background: #fff;
      box-shadow: 0 10px 28px rgb(15 23 42 / 8%);
    }
    h1 { margin-top: 0; font-size: 24px; }
    p { color: #526070; line-height: 1.55; }
    pre {
      overflow-x: auto;
      padding: 12px;
      border-radius: 10px;
      background: #0f172a;
      color: #e5e7eb;
    }
  </style>
</head>
<body>
  <main>
    <h1>Frontend build not found.</h1>
    <p>The /mobile page is now served from frontend/dist. Build the frontend first:</p>
    <pre>cd frontend
npm install
npm run build</pre>
  </main>
</body>
</html>"""


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "execution_mode": "agent_command",
        "session_mode": "agent_managed_app_server",
    }


@router.get("/", include_in_schema=False)
def index():
    return mobile_console()


@router.get("/mobile", include_in_schema=False)
def mobile_console():
    if FRONTEND_INDEX_HTML.exists():
        return FileResponse(FRONTEND_INDEX_HTML)
    return HTMLResponse(frontend_build_missing_page())
