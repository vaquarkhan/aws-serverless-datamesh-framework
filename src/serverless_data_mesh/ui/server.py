"""Mesh control UI HTTP server — dashboards, actions, tutorial assets."""

from __future__ import annotations

import json
import mimetypes
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from serverless_data_mesh.ui.data import build_dashboard, run_local_demo

_STATIC = Path(__file__).resolve().parent / "static"


def _tutorial_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parents[3] / "docs" / "images" / "tutorial",
        Path.cwd() / "docs" / "images" / "tutorial",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def serve_ui(
    *,
    generated_path: str | Path = "generated",
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
) -> None:
    root = Path(generated_path).resolve()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: Any) -> None:
            self._send(code, json.dumps(payload, indent=2).encode("utf-8"), "application/json")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path

            if path in ("/", "/index.html"):
                index = _STATIC / "index.html"
                self._send(200, index.read_bytes(), "text/html; charset=utf-8")
                return

            if path in ("/walkthrough", "/walkthrough.html", "/demo"):
                walk = (
                    Path(__file__).resolve().parents[3] / "docs" / "demo-walkthrough.html"
                )
                if not walk.is_file():
                    walk = Path.cwd() / "docs" / "demo-walkthrough.html"
                self._send(200, walk.read_bytes(), "text/html; charset=utf-8")
                return

            if path == "/api/dashboard":
                self._json(200, build_dashboard(root))
                return

            if path == "/api/status":
                dash = build_dashboard(root)
                self._json(
                    200,
                    {
                        "root": dash["root"],
                        "pipeline_count": dash["doctor"]["pipeline_count"],
                        "readers_done": dash["doctor"]["readers_done"],
                        "readers_total": dash["doctor"]["readers_total"],
                        "readers_pending": dash["doctor"]["readers_pending"],
                        "ready_to_deploy": dash["doctor"]["ready_to_deploy"],
                        "has_orchestrator": dash["doctor"]["has_orchestrator"],
                        "organization": dash.get("organization"),
                        "domains": dash.get("domains"),
                    },
                )
                return

            if path.startswith("/static/"):
                rel = path[len("/static/") :]
                file_path = (_STATIC / rel).resolve()
                if not str(file_path).startswith(str(_STATIC.resolve())) or not file_path.is_file():
                    self.send_error(404)
                    return
                ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
                self._send(200, file_path.read_bytes(), ctype)
                return

            if path.startswith("/tutorial/"):
                tutorial_root = _tutorial_dir()
                rel = path[len("/tutorial/") :]
                file_path = (tutorial_root / rel).resolve()
                if not str(file_path).startswith(str(tutorial_root.resolve())) or not file_path.is_file():
                    self.send_error(404)
                    return
                ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
                self._send(200, file_path.read_bytes(), ctype)
                return

            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", 0))
            _ = self.rfile.read(length) if length else b""

            if parsed.path == "/api/actions/demo":
                try:
                    result = run_local_demo(root)
                    self._json(200, result)
                except Exception as exc:
                    self._json(500, {"ok": False, "error": str(exc)})
                return

            if parsed.path == "/api/actions/attest-demo":
                try:
                    from serverless_data_mesh.local.runtime import LocalPVDMRuntime

                    runtime = LocalPVDMRuntime()
                    clean = runtime.run_write(workload_id="ui-attest", record_count=40)
                    marker = root / ".ui-demo-root"
                    marker.write_text(str(runtime.root), encoding="utf-8")
                    attest_root = runtime.root / "attestations"
                    files = list(attest_root.rglob("*.pvdma.json")) if attest_root.exists() else []
                    self._json(
                        200,
                        {
                            "ok": True,
                            "outcome": clean.outcome,
                            "proof_verdict": clean.proof_verdict,
                            "attestations": [str(p) for p in files],
                            "root": str(runtime.root),
                        },
                    )
                except Exception as exc:
                    self._json(500, {"ok": False, "error": str(exc)})
                return

            self.send_error(404)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"Mesh UI: {url}")
    print(f"  Generated: {root}")
    print(f"  Dashboard: {url}  ·  API: {url}api/dashboard")
    if open_browser:
        webbrowser.open(url)
    server.serve_forever()
