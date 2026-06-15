"""Lightweight mesh control UI (stdlib HTTP server)."""

from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


def _mesh_status(generated_path: Path) -> dict[str, Any]:
    from serverless_data_mesh.compile.wizard import doctor_generated

    doctor = doctor_generated(generated_path)
    manifest_path = generated_path / "mesh.manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    return {
        "root": str(generated_path),
        "pipeline_count": doctor.pipeline_count,
        "readers_done": doctor.readers_done,
        "readers_total": doctor.readers_total,
        "readers_pending": doctor.readers_pending,
        "ready_to_deploy": doctor.ready_to_deploy,
        "has_orchestrator": doctor.has_orchestrator,
        "organization": manifest.get("organization"),
        "domains": manifest.get("domains", []),
    }


def _html_page(status: dict[str, Any]) -> str:
    pending = "".join(f"<li><code>{p}</code></li>" for p in status.get("readers_pending", []))
    if not pending:
        pending = "<li class='ok'>All readers implemented</li>"
    domains = ", ".join(status.get("domains") or [])
    ready = "yes" if status.get("ready_to_deploy") else "no"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Serverless Data Mesh — Control UI</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin: 2rem; }}
    h1 {{ color: #38bdf8; }}
    .card {{ background: #1e293b; border-radius: 8px; padding: 1.25rem; margin: 1rem 0; max-width: 720px; }}
    .ok {{ color: #4ade80; }}
    code {{ background: #334155; padding: 2px 6px; border-radius: 4px; }}
    a {{ color: #7dd3fc; }}
  </style>
</head>
<body>
  <h1>Serverless Data Mesh</h1>
  <p>Metadata-driven medallion control panel</p>
  <div class="card">
    <p><strong>Generated:</strong> <code>{status.get("root")}</code></p>
    <p><strong>Organization:</strong> {status.get("organization") or "—"}</p>
    <p><strong>Domains:</strong> {domains or "—"}</p>
    <p><strong>Pipelines:</strong> {status.get("pipeline_count")}</p>
    <p><strong>Readers:</strong> {status.get("readers_done")}/{status.get("readers_total")}</p>
    <p><strong>Deploy ready:</strong> <span class="{'ok' if ready == 'yes' else ''}">{ready}</span></p>
    <p><strong>Pending readers:</strong></p>
    <ul>{pending}</ul>
  </div>
  <div class="card">
    <p><strong>CLI</strong></p>
    <pre>serverless-data-mesh apply --contract mesh.yaml --output generated
serverless-data-mesh deploy --contract mesh.yaml --dry-run
serverless-data-mesh dashboard --open</pre>
  </div>
  <p><a href="/api/status">JSON status</a> · refresh to update</p>
</body>
</html>"""


def serve_ui(
    *,
    generated_path: str | Path = "generated",
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
) -> None:
    root = Path(generated_path).resolve()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                status = _mesh_status(root)
                body = _html_page(status).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/api/status":
                body = json.dumps(_mesh_status(root), indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"Mesh UI: {url}")
    if open_browser:
        webbrowser.open(url)
    server.serve_forever()
