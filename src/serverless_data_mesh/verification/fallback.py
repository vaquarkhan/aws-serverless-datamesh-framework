"""Pure-Python multiset verifier when veridata-recon wheels are unavailable."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from serverless_data_mesh.types.workload import DataWriteWorkload


def _coerce_records(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{key: str(value) for key, value in record.items()} for record in records]


def _identity_rule(fields: tuple[str, ...]) -> str:
    if len(fields) == 1:
        return f"field:{fields[0]}"
    return f"composite:[{','.join(fields)}]"


def _record_fingerprint(
    record: dict[str, str],
    *,
    identity_fields: tuple[str, ...],
    content_fields: tuple[str, ...],
    salt: str,
) -> str:
    identity = "|".join(record.get(f, "") for f in identity_fields)
    content = "|".join(record.get(f, "") for f in content_fields)
    payload = f"{salt}:{identity}:{content}".encode()
    return hashlib.sha256(payload).hexdigest()


def reconcile_multiset(
    *,
    source: list[dict[str, Any]],
    sink: list[dict[str, Any]],
    identity_fields: tuple[str, ...],
    content_fields: tuple[str, ...],
    salt: str = "sdm-fallback-salt",
) -> dict[str, Any]:
    """Compare source and sink multisets; same verdict shape as veridata-recon."""
    src = _coerce_records(source)
    snk = _coerce_records(sink)

    src_fps = [
        _record_fingerprint(
            row,
            identity_fields=identity_fields,
            content_fields=content_fields,
            salt=salt,
        )
        for row in src
    ]
    snk_fps = [
        _record_fingerprint(
            row,
            identity_fields=identity_fields,
            content_fields=content_fields,
            salt=salt,
        )
        for row in snk
    ]

    src_counter = Counter(src_fps)
    snk_counter = Counter(snk_fps)

    missing: list[str] = []
    duplicated: list[str] = []
    mutated: list[str] = []

    all_keys = set(src_counter) | set(snk_counter)
    for key in sorted(all_keys):
        src_n = src_counter.get(key, 0)
        snk_n = snk_counter.get(key, 0)
        if snk_n < src_n:
            missing.extend([key] * (src_n - snk_n))
        if snk_n > src_n:
            duplicated.extend([key] * (snk_n - src_n))

    # Mutation: same identity, different content fingerprint in sink vs source
    if identity_fields:
        src_by_id: dict[str, str] = {}
        snk_by_id: dict[str, str] = {}
        for row in src:
            ident = "|".join(row.get(f, "") for f in identity_fields)
            fp = _record_fingerprint(
                row,
                identity_fields=identity_fields,
                content_fields=content_fields,
                salt=salt,
            )
            src_by_id[ident] = fp
        for row in snk:
            ident = "|".join(row.get(f, "") for f in identity_fields)
            fp = _record_fingerprint(
                row,
                identity_fields=identity_fields,
                content_fields=content_fields,
                salt=salt,
            )
            snk_by_id[ident] = fp
        for ident, src_fp in src_by_id.items():
            snk_fp = snk_by_id.get(ident)
            if snk_fp is not None and snk_fp != src_fp:
                mutated.append(ident)

    verdict = "PASS" if not missing and not duplicated and not mutated else "FAIL"
    return {
        "verdict": verdict,
        "missing": missing[:100],
        "duplicated": duplicated[:100],
        "mutated": mutated[:100],
        "source_count": len(src),
        "sink_count": len(snk),
        "backend": "pure-python-fallback",
    }


class FallbackProofGenerator:
    """Drop-in proof generator using pure-Python multiset reconciliation."""

    producer: str = "serverless-data-mesh/fallback-verifier"

    def __init__(self, *, salt_hex: str | None = None) -> None:
        self.salt_hex = salt_hex or uuid.uuid4().hex

    def build_proof(
        self,
        *,
        source_records: list[dict[str, Any]],
        sink_records: list[dict[str, Any]],
        workload: DataWriteWorkload,
        chunk_start: int,
        chunk_end: int,
        prev_proof_hash: str | None = None,
    ) -> dict[str, Any]:
        reconciliation = reconcile_multiset(
            source=source_records,
            sink=sink_records,
            identity_fields=workload.identity_fields,
            content_fields=workload.content_fields,
            salt=self.salt_hex,
        )
        boundary_value = base64.b64encode(
            json.dumps(
                {
                    "workload_id": workload.workload_id,
                    "domain_id": workload.boundary.domain_id,
                    "start": chunk_start,
                    "end": chunk_end,
                    "partition": workload.boundary.partition_spec,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).decode("ascii")

        document: dict[str, Any] = {
            "proof_version": "0.1-fallback",
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "producer": self.producer,
            "boundary": {"mode": "OFFSET_RANGE", "value": boundary_value},
            "source_ref": workload.source_uri,
            "sink_ref": workload.target_uri,
            "hash_algorithm": "sha256",
            "salt": self.salt_hex,
            "identity_rule": _identity_rule(workload.identity_fields),
            "content_fields": list(workload.content_fields),
            "reconciliation": reconciliation,
            "public_key": None,
            "chain": {"prev_proof_hash": prev_proof_hash},
        }
        document["proof_id"] = hashlib.sha256(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        return document

    def persist_proof(
        self,
        proof: dict[str, Any],
        *,
        bucket: str,
        key_prefix: str,
        chunk_index: int,
        s3_client: Any | None = None,
    ) -> str:
        from pathlib import Path

        root = Path(bucket)
        rel = f"{key_prefix.rstrip('/')}/proofs/chunk-{chunk_index:06d}.vrp.json"
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
        return f"file://{dest}"
