# Roadmap: PVDM-A and Agentic AI (not shipped)

Status: **design / future work**. Nothing in this document is present as runnable product code today.

The external architecture report describes PVDM-A, MCP, AgentCore Gateway, Presidio, and Bedrock Guardrails. Those claims are **aspirational** for this repository. This roadmap defines the smallest honest path to make them true.

---

## Principles (non-negotiable)

1. **Agents never bypass VRP.** Any write path still ends in `validate_then_commit` → metadata only on PASS.
2. **Agents never talk to raw lakehouse S3 for writes.** Tools call the same coordinator / Lambda handlers domains use.
3. **Decision provenance is additive.** PVDM-A attests *who decided* and *which proof* was linked — it does not replace VRP.
4. **Ship read-only MCP before write tools.** Reduce blast radius.

---

## Phase A — PVDM-A Decision Attestation (schema only → steward storage)

**Deliverable:** JSON schema + Python model + S3 persist helper.

```json
{
  "attestation_id": "pvdma-…",
  "agent_id": "bedrock-agent/…",
  "session_id": "…",
  "tool_name": "mesh.run_pipeline",
  "prompt_hash": "sha256:…",
  "tool_args_hash": "sha256:…",
  "workload_id": "…",
  "domain_id": "orders",
  "vrp_proof_uri": "s3://steward-proofs/…/chunk-000001.vrp.json",
  "vrp_verdict": "PASS",
  "decision": "allow_commit | deny | quarantine",
  "created_at": "2026-07-21T00:00:00Z"
}
```

**Storage:** Steward bucket prefix `attestations/{domain_id}/{workload_id}/`.

**CLI (later):** `serverless-data-mesh attest verify --uri s3://…`

---

## Phase B — MCP read-only tools

Expose Lambda-backed MCP tools (no AgentCore required for v1):

| Tool | Purpose |
|------|---------|
| `mesh.verify_proof` | Offline/online verify VRP JSON |
| `mesh.trust_metrics` | CloudWatch / local trust summary |
| `mesh.catalog_snapshot` | Read Iceberg snapshot id + table |
| `mesh.list_attestations` | List PVDM-A records for a workload |

**Auth (v1):** IAM SigV4 for Lambda URL or API Gateway. JWT / AgentCore Gateway = Phase C.

---

## Phase C — Zero-trust gateway (AgentCore-shaped)

Only after Phase B is stable:

- Request interceptor: JWT + scopes (`mesh:read`, `mesh:write`).
- Response interceptor: PII redaction (Presidio **or** AWS Comprehend) on any row samples.
- Optional Bedrock Guardrails / PromptGuard on tool inputs.

---

## Phase D — Crypto hardening (optional)

| Today | Roadmap |
|-------|---------|
| Keypair via `VRP_SIGNING_KEY_B64` | Optional **KMS Sign/Verify** for proof envelopes |
| Linear `prev_proof_hash` chain | Optional Merkle aggregation across chunks (only if auditors require it) |

Do **not** document Merkle/KMS as shipped until code exists.

---

## Explicitly out of scope for this Python framework

- Spring AI AgentCore Java OTel module (separate SDK/repo).
- Glue Data Quality Terraform workarounds (#38744 / #39821) unless Glue DQ becomes a product feature.
- Renaming PVDM to five phases — keep optional rules as **pre-Physical**, not Phase 0 of the pattern name.

---

## Acceptance criteria (when we can claim “agentic integration”)

- [ ] PVDM-A schema published and stored for at least one demo workload
- [ ] MCP read tools invoke without write privileges
- [ ] Attempted agent write without VRP PASS cannot commit metadata (integration test)
- [ ] Docs and README mark agentic features as **available**, not roadmap
- [ ] External architecture report updated to match

See also: [due-diligence-architecture-claims.md](due-diligence-architecture-claims.md)
