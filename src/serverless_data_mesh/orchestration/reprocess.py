"""Automatic VRP-triggered reprocessing: detect, repair, re-proof, commit or escalate."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from serverless_data_mesh.types.workload import DataWriteWorkload
from serverless_data_mesh.verification.backend import create_proof_generator
from serverless_data_mesh.verification.vrp import validate_then_commit

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReprocessResult:
    """Outcome of automatic repair after VRP FAIL."""

    outcome: str  # repaired_pass | escalated
    attempts: int
    missing_before: int
    missing_after: int
    final_verdict: str
    message: str
    proof: dict[str, Any] | None = None


def _identity_key(record: dict[str, Any], fields: tuple[str, ...]) -> str:
    return "|".join(str(record.get(f, "")) for f in fields)


def _find_missing_records(
    source: list[dict[str, Any]],
    sink: list[dict[str, Any]],
    identity_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    sink_ids = {_identity_key(r, identity_fields) for r in sink}
    return [r for r in source if _identity_key(r, identity_fields) not in sink_ids]


def attempt_vrp_repair(
    *,
    source_records: list[dict[str, Any]],
    sink_records: list[dict[str, Any]],
    workload: DataWriteWorkload,
    chunk_start: int,
    chunk_end: int,
    proof_generator: Any | None = None,
    max_attempts: int = 2,
    write_repair_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
) -> ReprocessResult:
    """On VRP FAIL, re-read missing records, repair sink, regenerate proof.

    Flow:
      VRP FAIL -> identify missing IDs -> merge into sink -> new VRP
      -> PASS: repaired_pass | still FAIL: escalated
    """
    if proof_generator is None:
        gen, _ = create_proof_generator()
    else:
        gen = proof_generator
    sink = list(sink_records)
    missing_before = len(
        _find_missing_records(source_records, sink, workload.identity_fields)
    )

    if missing_before == 0:
        proof = gen.build_proof(
            source_records=source_records,
            sink_records=sink,
            workload=workload,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
        )
        verdict = validate_then_commit(proof).outcome
        if verdict == "PASS":
            return ReprocessResult(
                outcome="repaired_pass",
                attempts=0,
                missing_before=0,
                missing_after=0,
                final_verdict=verdict,
                message="No missing records; original proof issue was mutation/duplicate",
                proof=proof,
            )
        return ReprocessResult(
            outcome="escalated",
            attempts=0,
            missing_before=0,
            missing_after=0,
            final_verdict=verdict,
            message="VRP FAIL without drops; escalate to human",
            proof=proof,
        )

    for attempt in range(1, max_attempts + 1):
        missing = _find_missing_records(source_records, sink, workload.identity_fields)
        if write_repair_fn:
            sink = write_repair_fn(missing)
        else:
            sink = sink + missing

        proof = gen.build_proof(
            source_records=source_records,
            sink_records=sink,
            workload=workload,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
        )
        verdict = validate_then_commit(proof).outcome
        missing_after = len(
            _find_missing_records(source_records, sink, workload.identity_fields)
        )

        logger.info(
            "VRP repair attempt %s: verdict=%s missing_before=%s missing_after=%s",
            attempt,
            verdict,
            missing_before,
            missing_after,
        )

        if verdict == "PASS":
            return ReprocessResult(
                outcome="repaired_pass",
                attempts=attempt,
                missing_before=missing_before,
                missing_after=missing_after,
                final_verdict=verdict,
                message=f"Repaired {missing_before} missing records on attempt {attempt}",
                proof=proof,
            )

    return ReprocessResult(
        outcome="escalated",
        attempts=max_attempts,
        missing_before=missing_before,
        missing_after=missing_after,
        final_verdict=verdict,
        message=f"VRP still FAIL after {max_attempts} repair attempts; escalate to human",
        proof=proof,
    )
