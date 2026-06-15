"""Run the Vaquar Pattern (PVDM) lifecycle on local disk without AWS."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from serverless_data_mesh.observability.structured import log_pvdm_outcome
from serverless_data_mesh.types.workload import (
    DataWriteWorkload,
    DomainTransactionBoundary,
    WriteOutcome,
)
from serverless_data_mesh.metrics.mesh_trust import publish_vrp_metric
from serverless_data_mesh.orchestration.reprocess import attempt_vrp_repair
from serverless_data_mesh.verification.backend import create_proof_generator
from serverless_data_mesh.verification.vrp import validate_then_commit


@dataclass(frozen=True, slots=True)
class LocalWriteResult:
    """Outcome of a local PVDM chunk write."""

    outcome: str
    workload_id: str
    records_written: int
    proof_verdict: str
    snapshot_id: str | None
    proof_path: str | None
    consumer_row_count: int
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _default_boundary() -> DomainTransactionBoundary:
    return DomainTransactionBoundary(
        domain_id="orders-domain",
        source_namespace="raw_orders",
        target_table="orders_curated",
        partition_spec={"dt": "2026-06-14"},
    )


def _proof_bucket_from_env() -> str | None:
    bucket = os.environ.get("VRP_PROOF_BUCKET") or os.environ.get("PROOF_BUCKET")
    return bucket.strip() if bucket else None


def _default_workload(root: Path, *, workload_id: str, total_records: int) -> DataWriteWorkload:
    boundary = _default_boundary()
    proof_bucket = _proof_bucket_from_env() or str(root / "proofs")
    return DataWriteWorkload(
        workload_id=workload_id,
        boundary=boundary,
        source_uri=f"file://{root}/source/",
        target_uri=f"file://{root}/lakehouse/orders_curated/",
        total_records=total_records,
        checkpoint_bucket=str(root / "checkpoints"),
        proof_bucket=proof_bucket,
    )


def _records(n: int, *, corrupt_last: bool = False) -> list[dict[str, str]]:
    rows = [{"id": str(i), "payload_hash": f"h{i}"} for i in range(n)]
    if corrupt_last and rows:
        rows[-1] = {"id": rows[-1]["id"], "payload_hash": "CORRUPT"}
    return rows


class LocalPVDMRuntime:
    """Simulate Physical → Verify → Durable → Metadata on a laptop.

    Uses veridata-recon when available; pure-Python fallback on Windows/Mac without wheels.
    Checkpoints, proofs, and catalog snapshots are stored on local disk.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(tempfile.mkdtemp(prefix="sdm-demo-"))
        self.checkpoints = self.root / "checkpoints"
        self.proofs = self.root / "proofs"
        self.lakehouse = self.root / "lakehouse" / "orders_curated" / "dt=2026-06-14"
        self.catalog = self.root / "catalog"
        for path in (self.checkpoints, self.proofs, self.lakehouse, self.catalog):
            path.mkdir(parents=True, exist_ok=True)
        self._snapshot_file = self.catalog / "snapshots.json"
        if not self._snapshot_file.exists():
            self._snapshot_file.write_text("[]", encoding="utf-8")

    @property
    def consumer_row_count(self) -> int:
        """Rows visible to consumers from the latest committed snapshot."""
        snapshots = json.loads(self._snapshot_file.read_text(encoding="utf-8"))
        if not snapshots:
            return 0
        return int(snapshots[-1]["row_count"])

    def _persist_proof(
        self,
        proof: dict[str, Any],
        *,
        workload: DataWriteWorkload,
        chunk_index: int,
    ) -> Path | str:
        rel = f"{workload.boundary.domain_id}/{workload.workload_id}"
        key = f"{rel}/proofs/chunk-{chunk_index:06d}.vrp.json"
        body = json.dumps(proof, indent=2, sort_keys=True).encode("utf-8")
        verdict = proof["reconciliation"]["verdict"]
        bucket = _proof_bucket_from_env()

        if bucket and not bucket.startswith("/") and "://" not in bucket:
            try:
                import boto3

                boto3.client("s3").put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=body,
                    ContentType="application/json",
                    Metadata={"proof-id": proof["proof_id"], "verdict": verdict},
                )
                uri = f"s3://{bucket}/{key}"
                log_pvdm_outcome(
                    outcome="proof_persisted",
                    storage="s3",
                    proof_uri=uri,
                    verdict=verdict,
                    proof_id=proof["proof_id"],
                    domain_id=workload.boundary.domain_id,
                    workload_id=workload.workload_id,
                )
                return uri
            except Exception as exc:
                log_pvdm_outcome(
                    outcome="proof_persist_failed",
                    storage="s3",
                    error=str(exc),
                    domain_id=workload.boundary.domain_id,
                    workload_id=workload.workload_id,
                )

        dest_dir = self.proofs / rel
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / f"chunk-{chunk_index:06d}.vrp.json"
        path.write_bytes(body)
        log_pvdm_outcome(
            outcome="proof_persisted",
            storage="local",
            proof_path=str(path),
            verdict=verdict,
            proof_id=proof["proof_id"],
            domain_id=workload.boundary.domain_id,
            workload_id=workload.workload_id,
        )
        return path

    def _write_physical(self, records: list[dict[str, str]], *, part_name: str) -> Path:
        part = self.lakehouse / f"{part_name}.jsonl"
        with part.open("w", encoding="utf-8") as handle:
            for row in records:
                handle.write(json.dumps(row) + "\n")
        return part

    def _commit_metadata(self, *, workload: DataWriteWorkload, row_count: int, proof_id: str) -> str:
        snapshots = json.loads(self._snapshot_file.read_text(encoding="utf-8"))
        snapshot_id = f"snap-{len(snapshots) + 1:06d}"
        snapshots.append(
            {
                "snapshot_id": snapshot_id,
                "table": workload.boundary.target_table,
                "partition": workload.boundary.partition_spec,
                "row_count": row_count,
                "proof_id": proof_id,
                "committed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            }
        )
        self._snapshot_file.write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
        checkpoint = self.checkpoints / f"{workload.workload_id}.json"
        checkpoint.write_text(
            json.dumps({"workload_id": workload.workload_id, "snapshot_id": snapshot_id}),
            encoding="utf-8",
        )
        return snapshot_id

    def run_write(
        self,
        *,
        workload_id: str = "local-demo-001",
        record_count: int = 1000,
        corrupt_sink: bool = False,
        proof_generator: Any | None = None,
        defer_snapshot: bool = False,
    ) -> LocalWriteResult:
        """Execute one PVDM write cycle on local disk."""
        started = time.perf_counter()
        workload = _default_workload(self.root, workload_id=workload_id, total_records=record_count)
        if proof_generator is None:
            gen, self._last_backend = create_proof_generator()
        else:
            gen = proof_generator
            self._last_backend = getattr(gen, "producer", "custom")

        source = _records(record_count)
        sink = _records(record_count, corrupt_last=corrupt_sink)

        self._write_physical(sink, part_name=f"{workload_id}-part-00000")

        proof = gen.build_proof(
            source_records=source,
            sink_records=sink,
            workload=workload,
            chunk_start=0,
            chunk_end=record_count,
        )
        verification = validate_then_commit(proof)
        proof_path = self._persist_proof(proof, workload=workload, chunk_index=0)
        verdict = proof["reconciliation"]["verdict"]
        publish_vrp_metric(
            domain_id=workload.boundary.domain_id,
            verdict=verdict,
            row_count=record_count,
            workload_id=workload_id,
        )

        if verification.outcome != "PASS":
            log_pvdm_outcome(
                outcome=WriteOutcome.VERIFICATION_FAILED.value,
                domain_id=workload.boundary.domain_id,
                workload_id=workload_id,
                rows=0,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
                proof_id=proof.get("proof_id"),
                verdict=verdict,
            )
            return LocalWriteResult(
                outcome=WriteOutcome.VERIFICATION_FAILED.value,
                workload_id=workload_id,
                records_written=0,
                proof_verdict=verdict,
                snapshot_id=None,
                proof_path=str(proof_path),
                consumer_row_count=self.consumer_row_count,
                message=verification.reason,
            )

        if defer_snapshot:
            pending = self.catalog / "pending.json"
            pending_rows = []
            if pending.exists():
                pending_rows = json.loads(pending.read_text(encoding="utf-8"))
            pending_rows.append(
                {
                    "workload_id": workload_id,
                    "row_count": record_count,
                    "proof_id": proof["proof_id"],
                }
            )
            pending.write_text(json.dumps(pending_rows, indent=2), encoding="utf-8")
            log_pvdm_outcome(
                outcome=WriteOutcome.COMMITTED.value,
                domain_id=workload.boundary.domain_id,
                workload_id=workload_id,
                rows=record_count,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
                proof_id=proof["proof_id"],
                verdict=verdict,
                deferred_snapshot=True,
            )
            return LocalWriteResult(
                outcome=WriteOutcome.COMMITTED.value,
                workload_id=workload_id,
                records_written=record_count,
                proof_verdict=verdict,
                snapshot_id=None,
                proof_path=str(proof_path),
                consumer_row_count=self.consumer_row_count,
                message="VRP PASS; snapshot deferred for mesh leader commit",
            )

        snapshot_id = self._commit_metadata(
            workload=workload,
            row_count=record_count,
            proof_id=proof["proof_id"],
        )
        log_pvdm_outcome(
            outcome=WriteOutcome.COMMITTED.value,
            domain_id=workload.boundary.domain_id,
            workload_id=workload_id,
            rows=record_count,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            proof_id=proof["proof_id"],
            snapshot_id=snapshot_id,
            verdict=verdict,
        )
        return LocalWriteResult(
            outcome=WriteOutcome.COMMITTED.value,
            workload_id=workload_id,
            records_written=record_count,
            proof_verdict=verdict,
            snapshot_id=snapshot_id,
            proof_path=str(proof_path),
            consumer_row_count=self.consumer_row_count,
        )

    def finalize_mesh_transaction(self, domain_results: list[LocalWriteResult]) -> dict[str, Any]:
        """Leader commit: all domains must VRP PASS or no consumer snapshot."""
        pending_file = self.catalog / "pending.json"
        if any(r.outcome != WriteOutcome.COMMITTED.value for r in domain_results):
            if pending_file.exists():
                pending_file.unlink()
            return {
                "mesh_outcome": WriteOutcome.VERIFICATION_FAILED.value,
                "consumer_row_count": self.consumer_row_count,
                "message": "At least one domain failed VRP; pending snapshots discarded",
            }

        if not pending_file.exists():
            return {
                "mesh_outcome": WriteOutcome.VERIFICATION_FAILED.value,
                "consumer_row_count": self.consumer_row_count,
                "message": "No pending domain writes",
            }

        pending_rows = json.loads(pending_file.read_text(encoding="utf-8"))
        total_rows = sum(int(row["row_count"]) for row in pending_rows)
        proof_id = pending_rows[-1]["proof_id"]
        workload = _default_workload(self.root, workload_id="mesh-txn", total_records=total_rows)
        snapshot_id = self._commit_metadata(
            workload=workload,
            row_count=total_rows,
            proof_id=proof_id,
        )
        pending_file.unlink()
        return {
            "mesh_outcome": WriteOutcome.COMMITTED.value,
            "snapshot_id": snapshot_id,
            "consumer_row_count": self.consumer_row_count,
            "domains_committed": len(domain_results),
        }

    def run_write_with_auto_repair(
        self,
        *,
        workload_id: str = "auto-repair-demo",
        record_count: int = 100,
        drop_count: int = 5,
        proof_generator: Any | None = None,
    ) -> dict[str, Any]:
        """Simulate dropped records, auto-repair via VRP reprocessing, then commit."""
        workload = _default_workload(self.root, workload_id=workload_id, total_records=record_count)
        if proof_generator is None:
            gen, backend = create_proof_generator()
        else:
            gen = proof_generator
            backend = getattr(gen, "producer", "custom")

        source = _records(record_count)
        sink = _records(record_count - drop_count)
        repaired_sink = list(sink)

        def _merge_missing(missing: list[dict[str, str]]) -> list[dict[str, str]]:
            nonlocal repaired_sink
            repaired_sink = repaired_sink + missing
            return repaired_sink

        repair = attempt_vrp_repair(
            source_records=source,
            sink_records=sink,
            workload=workload,
            chunk_start=0,
            chunk_end=record_count,
            proof_generator=gen,
            write_repair_fn=_merge_missing,
        )

        if repair.outcome != "repaired_pass" or repair.proof is None:
            return {
                "outcome": repair.outcome,
                "backend": backend,
                "repair": {
                    "outcome": repair.outcome,
                    "attempts": repair.attempts,
                    "missing_before": repair.missing_before,
                    "missing_after": repair.missing_after,
                    "message": repair.message,
                },
                "consumer_row_count": self.consumer_row_count,
            }

        self._write_physical(repaired_sink, part_name=f"{workload_id}-repaired")
        proof_path = self._persist_proof(repair.proof, workload=workload, chunk_index=0)
        publish_vrp_metric(
            domain_id=workload.boundary.domain_id,
            verdict="PASS",
            row_count=record_count,
            workload_id=workload_id,
        )
        snapshot_id = self._commit_metadata(
            workload=workload,
            row_count=record_count,
            proof_id=repair.proof["proof_id"],
        )
        return {
            "outcome": "repaired_and_committed",
            "backend": backend,
            "repair": {
                "outcome": repair.outcome,
                "attempts": repair.attempts,
                "missing_before": repair.missing_before,
                "missing_after": repair.missing_after,
                "message": repair.message,
            },
            "snapshot_id": snapshot_id,
            "proof_path": str(proof_path),
            "consumer_row_count": self.consumer_row_count,
        }

    def run_demo_sequence(self) -> dict[str, Any]:
        """Run clean write, corrupt write, and consumer visibility check."""
        gen, backend = create_proof_generator()

        started = time.perf_counter()
        clean = self.run_write(
            workload_id="demo-clean",
            record_count=1000,
            corrupt_sink=False,
            proof_generator=gen,
        )
        corrupt = self.run_write(
            workload_id="demo-corrupt",
            record_count=1000,
            corrupt_sink=True,
            proof_generator=gen,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)

        return {
            "mode": "local-pvdm",
            "verifier_backend": backend,
            "root": str(self.root),
            "elapsed_ms": elapsed_ms,
            "phases": {
                "clean_write": clean.to_dict(),
                "corrupt_write": corrupt.to_dict(),
            },
            "consumer": {
                "visible_row_count": self.consumer_row_count,
                "corrupt_data_visible": corrupt.outcome == WriteOutcome.COMMITTED.value,
                "gate_blocked_bad_data": corrupt.outcome == WriteOutcome.VERIFICATION_FAILED.value,
            },
            "summary": (
                "VRP gate blocked corrupt write; consumers see only clean snapshot."
                if corrupt.outcome == WriteOutcome.VERIFICATION_FAILED.value
                else "Unexpected: corrupt write committed."
            ),
        }
