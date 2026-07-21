"""HTTP smoke tests for mesh control UI server handlers."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from serverless_data_mesh.ui.server import serve_ui


@pytest.fixture()
def generated(tmp_path: Path) -> Path:
    (tmp_path / "mesh.manifest.json").write_text(
        json.dumps({"organization": "t", "domains": ["orders"]}),
        encoding="utf-8",
    )
    (tmp_path / "mesh.orchestrator.asl.json").write_text("{}", encoding="utf-8")
    (tmp_path / "orders" / "bronze").mkdir(parents=True)
    (tmp_path / "orders" / "bronze" / "readers.py").write_text(
        "def source_reader(s,e): return []\n",
        encoding="utf-8",
    )
    (tmp_path / "orders" / "bronze" / "handler.py").write_text("#\n", encoding="utf-8")
    return tmp_path


def test_ui_http_endpoints(generated: Path) -> None:
    import urllib.error
    import urllib.request

    port = 18765
    thread = threading.Thread(
        target=serve_ui,
        kwargs={"generated_path": generated, "host": "127.0.0.1", "port": port},
        daemon=True,
    )
    thread.start()

    import time

    for _ in range(40):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=0.5) as resp:
                assert resp.status == 200
                break
        except Exception:
            time.sleep(0.05)
    else:
        pytest.fail("UI server did not start")

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        html = resp.read().decode("utf-8")
        assert "Control Center" in html or "Serverless Data Mesh" in html

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/dashboard") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert "kpis" in data

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status") as resp:
        status = json.loads(resp.read().decode("utf-8"))
        assert status["organization"] == "t"

    # walkthrough may 200 if docs present
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/walkthrough") as resp:
            assert resp.status == 200
    except urllib.error.HTTPError as exc:
        assert exc.code in (200, 404)

    # 404
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/nope")
    assert err.value.code == 404

    # POST demo
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/actions/demo",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        assert body.get("ok") is True

    req2 = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/actions/attest-demo",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req2) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        assert body.get("ok") is True
