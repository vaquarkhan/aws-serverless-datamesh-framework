"""PVDM cryptographic primitives aligned with the VLDB reference gate.

Ported from ``validation/pvdm_gate.py`` in
https://github.com/vaquarkhan/Proof-gated-publication-PVDM (Apache-2.0)
so this production framework satisfies normative MUST items N1, N3–N5, N10.

Author of method: Vaquar / Viquar Khan. Code in this file: Apache-2.0.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

MOD = 2**256


def canonical_row(row: Mapping[str, Any], fields: Iterable[str] | None = None) -> bytes:
    """Deterministic byte encoding of a row projection (L8 / N6 / N14 light)."""
    if fields is not None:
        projected = {k: row.get(k) for k in fields}
    else:
        projected = dict(row)
    return json.dumps(projected, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )


def _element_hash(key: bytes, blob: bytes) -> int:
    return int.from_bytes(hmac.new(key, blob, hashlib.sha256).digest(), "big")


def multiset_hash(
    rows: Iterable[Mapping[str, Any]],
    key: bytes,
    fields: Iterable[str] | None = None,
) -> int:
    """Keyed MSet-Add-Hash: sum of HMAC-SHA256 element hashes mod 2**256 (N1, N3)."""
    acc = 0
    for row in rows:
        acc = (acc + _element_hash(key, canonical_row(row, fields))) % MOD
    return acc


def digest_hex(value: int) -> str:
    """Stable hex encoding of a 256-bit multiset digest."""
    return format(value % MOD, "064x")


def file_digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _decode_key(raw: str) -> bytes:
    text = raw.strip()
    if text.startswith("hex:"):
        return bytes.fromhex(text[4:])
    if text.startswith("b64:"):
        import base64

        return base64.b64decode(text[4:])
    # Prefer hex when it looks like hex; else UTF-8 secret material.
    try:
        if len(text) >= 32 and all(c in "0123456789abcdefABCDEF" for c in text):
            return bytes.fromhex(text)
    except ValueError:
        pass
    return text.encode("utf-8")


def vrp_hmac_key_from_env() -> bytes | None:
    """Steward-held multiset key (N1/N2/N17). Prefer Steward runtime only."""
    raw = os.environ.get("SDM_VRP_HMAC_KEY") or os.environ.get("VRP_STEWARD_HMAC_KEY")
    if raw:
        return _decode_key(raw)
    if unsigned_proofs_allowed():
        return hashlib.sha256(b"sdm-demo-unsigned-not-conformant").digest()
    return None


def steward_sign_key_from_env() -> bytes | None:
    """Steward proof-signing key (N5). Falls back to multiset key when unset."""
    raw = os.environ.get("SDM_STEWARD_SIGN_KEY") or os.environ.get("VRP_STEWARD_SIGN_KEY")
    if raw:
        return _decode_key(raw)
    return vrp_hmac_key_from_env()


def unsigned_proofs_allowed() -> bool:
    """N10 escape hatch for local demos only — not PVDM-conformant."""
    return os.environ.get("SDM_ALLOW_UNSIGNED_PROOF", "").lower() in ("1", "true", "yes")


def require_steward_keys() -> tuple[bytes, bytes]:
    """Return (vrp_key, steward_sign_key) or raise if unsigned not allowed."""
    vrp_key = vrp_hmac_key_from_env()
    sign_key = steward_sign_key_from_env()
    if vrp_key is None or sign_key is None:
        raise RuntimeError(
            "PVDM N1/N5 require Steward keys: set SDM_VRP_HMAC_KEY and "
            "SDM_STEWARD_SIGN_KEY (Steward account only). For non-conformant "
            "local demos only, set SDM_ALLOW_UNSIGNED_PROOF=1."
        )
    return vrp_key, sign_key


@dataclass
class PvdmBinding:
    """Signed Verify→Metadata binding (Theorems 1–3 / N5)."""

    workload_id: str
    chunk_id: str
    target: str
    partition: str
    identity_hash: str
    content_hash: str
    file_digests: dict[str, str]
    nonce: str
    verdict: str
    key_epoch: str = "e1"
    profile: str = "A"
    steward_signature: str = ""

    def body(self) -> bytes:
        return json.dumps(
            {
                "workload_id": self.workload_id,
                "chunk_id": self.chunk_id,
                "target": self.target,
                "partition": self.partition,
                "identity_hash": self.identity_hash,
                "content_hash": self.content_hash,
                "file_digests": self.file_digests,
                "nonce": self.nonce,
                "verdict": self.verdict,
                "key_epoch": self.key_epoch,
                "profile": self.profile,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def sign(self, steward_key: bytes) -> PvdmBinding:
        self.steward_signature = hmac.new(steward_key, self.body(), hashlib.sha256).hexdigest()
        return self

    def verify_signature(self, steward_key: bytes) -> bool:
        if not self.steward_signature:
            return False
        expected = hmac.new(steward_key, self.body(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.steward_signature)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workload_id": self.workload_id,
            "chunk_id": self.chunk_id,
            "target": self.target,
            "partition": self.partition,
            "identity_hash": self.identity_hash,
            "content_hash": self.content_hash,
            "file_digests": dict(self.file_digests),
            "nonce": self.nonce,
            "verdict": self.verdict,
            "key_epoch": self.key_epoch,
            "profile": self.profile,
            "steward_signature": self.steward_signature,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PvdmBinding:
        return cls(
            workload_id=str(data["workload_id"]),
            chunk_id=str(data["chunk_id"]),
            target=str(data["target"]),
            partition=str(data.get("partition") or ""),
            identity_hash=str(data["identity_hash"]),
            content_hash=str(data["content_hash"]),
            file_digests={str(k): str(v) for k, v in (data.get("file_digests") or {}).items()},
            nonce=str(data["nonce"]),
            verdict=str(data.get("verdict") or "UNSET"),
            key_epoch=str(data.get("key_epoch") or "e1"),
            profile=str(data.get("profile") or "A"),
            steward_signature=str(data.get("steward_signature") or ""),
        )


def _partition_str(partition: Any) -> str:
    if partition is None:
        return ""
    if isinstance(partition, str):
        return partition
    return json.dumps(partition, sort_keys=True, separators=(",", ":"), default=str)


def build_pvdm_binding(
    *,
    workload_id: str,
    chunk_id: str,
    target: str,
    partition: Any,
    intended_rows: list[Mapping[str, Any]],
    written_rows: list[Mapping[str, Any]],
    identity_fields: tuple[str, ...] | list[str],
    file_digests: list[dict[str, str]] | dict[str, str],
    vrp_key: bytes,
    steward_key: bytes,
    nonce: str | None = None,
    key_epoch: str = "e1",
    profile: str | None = None,
    reconciliation_verdict: str | None = None,
) -> PvdmBinding:
    """Compute keyed digests, combine with file digests, Steward-sign (Verify)."""
    id_fields = list(identity_fields)
    id_src = multiset_hash(intended_rows, vrp_key, id_fields)
    id_snk = multiset_hash(written_rows, vrp_key, id_fields)
    ct_src = multiset_hash(intended_rows, vrp_key)
    ct_snk = multiset_hash(written_rows, vrp_key)
    keyed_pass = id_src == id_snk and ct_src == ct_snk

    if isinstance(file_digests, list):
        digest_map = {item["path"]: item.get("sha256", "") for item in file_digests}
    else:
        digest_map = dict(file_digests)

    verdict = "PASS" if keyed_pass else "FAIL"
    if reconciliation_verdict and reconciliation_verdict != "PASS":
        verdict = "FAIL"
    if reconciliation_verdict == "PASS" and not keyed_pass:
        verdict = "FAIL"

    binding = PvdmBinding(
        workload_id=workload_id,
        chunk_id=chunk_id,
        target=target,
        partition=_partition_str(partition),
        identity_hash=digest_hex(id_snk),
        content_hash=digest_hex(ct_snk),
        file_digests=digest_map,
        nonce=nonce or secrets.token_hex(16),
        verdict=verdict,
        key_epoch=key_epoch,
        profile=profile or os.environ.get("SDM_PVDM_PROFILE", "A"),
    )
    return binding.sign(steward_key)


def new_nonce() -> str:
    return secrets.token_hex(16)
