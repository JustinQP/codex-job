from __future__ import annotations


def mobile_console() -> str:
    """Compatibility helper for tests and older imports.

    The real mobile UI is now built from frontend/ and served by backend.main.
    """
    return frontend_build_missing_page()


def frontend_build_missing_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Frontend build not found</title>
</head>
<body>
  <main>
    <h1>Frontend build not found.</h1>
    <p>The /mobile page is served from frontend/dist.</p>
    <pre>cd frontend
npm install
npm run build</pre>
  </main>
</body>
</html>"""
