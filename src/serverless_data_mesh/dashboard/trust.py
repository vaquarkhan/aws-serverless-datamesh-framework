"""Mesh trust dashboard: real-time VRP status per domain."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from serverless_data_mesh.dashboard.cloudwatch import fetch_cloudwatch_trust_rows


def _demo_rows() -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).strftime("%I:%M %p")
    return [
        {"domain": "orders", "last_vrp": now, "status": "PASS", "rows": "5.2M", "detail": ""},
        {"domain": "payments", "last_vrp": now, "status": "PASS", "rows": "1.1M", "detail": ""},
        {
            "domain": "inventory",
            "last_vrp": "09:45 AM",
            "status": "FAIL",
            "rows": "0",
            "detail": "3 drops detected",
        },
        {"domain": "shipping", "last_vrp": now, "status": "PASS", "rows": "800K", "detail": ""},
    ]


def _scan_proofs(proofs_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proof_file in sorted(proofs_dir.rglob("*.vrp.json")):
        try:
            data = json.loads(proof_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        recon = data.get("reconciliation", {})
        verdict = recon.get("verdict", "UNKNOWN")
        domain = proof_file.parts[-3] if len(proof_file.parts) >= 3 else "unknown"
        created = data.get("created_at", "")[:16].replace("T", " ")
        rows.append(
            {
                "domain": domain,
                "last_vrp": created or "unknown",
                "status": verdict,
                "rows": str(recon.get("sink_count", "?")),
                "detail": _fail_detail(recon) if verdict == "FAIL" else "",
            }
        )
    return rows or _demo_rows()


def _fail_detail(recon: dict[str, Any]) -> str:
    missing = len(recon.get("missing", []))
    mutated = len(recon.get("mutated", []))
    dup = len(recon.get("duplicated", []))
    parts = []
    if missing:
        parts.append(f"{missing} drops")
    if mutated:
        parts.append(f"{mutated} mutations")
    if dup:
        parts.append(f"{dup} duplicates")
    return ", ".join(parts) or "reconciliation failed"


def render_trust_dashboard(
    *,
    proofs_dir: str | None = None,
    output: str = "mesh-trust-dashboard.html",
    demo: bool = False,
    cloudwatch: bool = False,
    cloudwatch_region: str | None = None,
) -> Path:
    """Render HTML trust dashboard from proofs, CloudWatch, or demo data."""
    if cloudwatch:
        rows = fetch_cloudwatch_trust_rows(region=cloudwatch_region)
        mode = "cloudwatch"
        if not rows:
            rows = _demo_rows()
            mode = "cloudwatch-fallback-demo"
    elif demo or not proofs_dir:
        rows = _demo_rows()
        mode = "demo"
    else:
        rows = _scan_proofs(Path(proofs_dir))
        mode = "live-proofs"

    html = HTML_TEMPLATE.format(
        generated_at=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        rows=_render_rows(rows),
        pass_count=sum(1 for r in rows if r["status"] == "PASS"),
        fail_count=sum(1 for r in rows if r["status"] == "FAIL"),
        total=len(rows),
    )
    out = Path(output)
    out.write_text(html, encoding="utf-8")
    return out.resolve()


def _render_rows(rows: list[dict[str, Any]]) -> str:
    lines = []
    for row in rows:
        if row["status"] == "PASS":
            icon = "PASS"
            cls = "pass"
        elif row["status"] == "FAIL":
            icon = "FAIL"
            cls = "fail"
        else:
            icon = "PENDING"
            cls = "pending"
        detail = f" ({row['detail']})" if row.get("detail") else ""
        lines.append(
            f"<tr class='{cls}'><td>{row['domain']}</td>"
            f"<td>{row['last_vrp']}</td>"
            f"<td><span class='badge {cls}'>{icon}</span></td>"
            f"<td>{row['rows']}{detail}</td></tr>"
        )
    return "\n".join(lines)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Mesh Trust Dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin: 2rem; }}
    h1 {{ color: #38bdf8; }}
    .summary {{ display: flex; gap: 1.5rem; margin: 1.5rem 0; }}
    .card {{ background: #1e293b; padding: 1rem 1.5rem; border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #334155; }}
    th {{ color: #94a3b8; }}
    tr.pass td {{ }}
    tr.fail {{ background: #450a0a33; }}
    .badge {{ padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 600; font-size: 0.85rem; }}
    .badge.pass {{ background: #14532d; color: #86efac; }}
    .badge.fail {{ background: #7f1d1d; color: #fca5a5; }}
    .badge.pending {{ background: #713f12; color: #fde68a; }}
    .meta {{ color: #64748b; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>Mesh Trust Dashboard</h1>
  <p class="meta">Vaquar Pattern (PVDM) · mode: {mode} · generated {generated_at}</p>
  <div class="summary">
    <div class="card"><strong>{total}</strong> domains</div>
    <div class="card"><strong>{pass_count}</strong> PASS</div>
    <div class="card"><strong>{fail_count}</strong> FAIL</div>
  </div>
  <table>
    <thead><tr><th>Domain</th><th>Last VRP</th><th>Status</th><th>Rows / Detail</th></tr></thead>
    <tbody>
    {rows}
    </tbody>
  </table>
  <p class="meta">Invariant: commit_metadata implies VRP = PASS</p>
</body>
</html>
"""
