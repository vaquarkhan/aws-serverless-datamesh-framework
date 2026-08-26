# Due diligence: architecture report vs this repository

**Branch:** `review/pvdm-agentic-due-diligence`  
**Source reviewed:** *Architecture and Implementation of the AWS Serverless Data Mesh Framework: PVDM, Durable Execution, and Agentic AI Integration*  
**Repo under audit:** [aws-serverless-datamesh-framework](https://github.com/vaquarkhan/aws-serverless-datamesh-framework)

This document separates **what is true today**, **what is overstated**, and **what would add real product value** if built.

---

## Executive verdict

| Category | Assessment |
|----------|------------|
| **Core mesh (PVDM × 4, IceGuard, VRP gate, Durable + Step Functions, Glue/PyIceberg, three-account, medallion YAML, observability)** | **Accurate and shippable** — this is the real product |
| **Crypto wording (Merkle trees, KMS-signed VRP)** | **Overstated** — SHA-256 + keypair signing + hash chain; not Merkle / not KMS Sign |
| **Orchestration wording (Step Functions “continuation tokens”)** | **Misstated** — resume is outcome=`rolled_back` re-invoke + Durable checkpoints |
| **“Five-phase PVDM” / mandatory Phase 0 Rules** | **Misstated** — SparkRules is **optional** pre-Physical; canonical PVDM is **four** phases |
| **Agentic AI (PVDM-A, MCP, AgentCore, Presidio, PromptGuard, Spring AI OTel)** | **Not in this repo** — treat as roadmap, not current capability |
| **Terraform Glue DQ bugs #38744 / #39821** | **Not applicable here** — no Glue Data Quality Terraform resources |
| **`.cursorrules` / Memory Bank** | **Were missing** — Cursor rules added on this branch; Memory Bank still optional |

**Bottom line:** Use the report as a **vision + marketing overlay**. Do **not** publish it as a faithful description of this repository until claims 1–3 are corrected and agentic sections are labeled “roadmap.”

---

## Claim-by-claim scorecard

| # | Report claim | Status | Evidence | Fix |
|---|--------------|--------|----------|-----|
| 1 | PVDM has **5** phases; Phase 0 Rules is mandatory | **MISSTATED** | `docs/vaquar-pattern.md` — four phases P·V·D·M; SparkRules optional | Correct all external copy |
| 2 | VRP = SHA-256 + **Merkle** + **KMS-signed** | **PARTIAL** | `verification/vrp.py` — SHA-256, keypair (`VRP_SIGNING_KEY_B64`), hash chain | Say “keypair-signed”; KMS Sign = future |
| 3 | IceGuard + SFN **continuation tokens** | **PARTIAL** | IceGuard rollback real; SFN Choice/Wait re-invoke on `rolled_back` | Drop “continuation token” language |
| 4 | GlueCatalogConnector / proof-gated Iceberg commit | **EXISTS** | `catalog/`, coordinator `validate_then_commit` | Keep |
| 5 | PVDM-A Decision Attestation | **MISSING** | No code/docs | Spec + stub if agent story matters |
| 6 | MCP / AgentCore Gateway / JWT interceptors | **MISSING** | No MCP surface | Build MCP read tools only after PVDM-A |
| 7 | Microsoft Presidio on MCP responses | **MISSING** | — | Required if MCP returns rows |
| 8 | PromptGuard / Bedrock Guardrails | **MISSING** | — | Optional when LLM tools exist |
| 9 | Spring AI AgentCore observability (Java) | **MISSING** | Python-only repo | Out of scope unless separate SDK |
| 10 | Terraform Glue DQ `join()` (#38744) | **MISSING** | No `aws_glue_data_quality*` | Do not invent; N/A |
| 11 | Glue `data_quality_encryption` (#39821) | **MISSING** | — | N/A unless Glue DQ adopted |
| 12 | `.cursorrules` enforcing PVDM | **ADDED** on this branch | `.cursorrules` | Keep updated with invariants |
| 13 | `.cursor/memory/` Memory Bank | **MISSING** | — | Optional DX |
| 14 | AWS Durable SDK + Step Functions | **EXISTS** | handler durable + SFN module | Keep dual model |
| 15 | Producer / Steward / Publisher | **EXISTS** | `environments/multi-account/` | Keep |
| 16 | Medallion / YAML compiler | **EXISTS** | `compile/medallion*.py` | Keep |
| 17 | Structured logs, CW metrics, DLQ, dashboard | **EXISTS** | `observability-production.md` | Keep |

---

## What the product actually is

```text
[optional SparkRules DRL]
        │
        ▼
Physical (IceGuard SafeWriter + S3 checkpoints + timeout rollback)
        │
        ▼
Verify   (veridata-recon VRP / SHA-256 + keypair + hash chain)
        │
        ▼
Durable  (AWS Durable Execution SDK + Step Functions resume on rolled_back)
        │
        ▼
Metadata (GlueCatalogConnector / PyIceberg — only if VRP = PASS)
```

**Invariant (canonical):** `commit_metadata ⟹ VRP = PASS`

**VLDB paper alignment (this repository is the production PVDM implementation):**

| Paper MUST | Production mapping in this repo |
|------------|----------------------------------|
| N1 keyed MSet-Add-Hash | `verification/pvdm_primitives.multiset_hash` (HMAC-SHA256, mod 2^256) via `SDM_VRP_HMAC_KEY` |
| N4 file digests + re-hash | `metadata_commit_gate` TOCTOU check |
| N5 Steward sign + nonce + target | `pvdm_binding` on every proof; nonce ledger; target match at commit |
| N10 no unsigned override | keys required unless `SDM_ALLOW_UNSIGNED_PROOF=1` (demo only) |
| P·V·D·M phases | IceGuard → VRP+keyed binding → Durable SDK → Glue/PyIceberg behind commit gate |

**Paper & artifacts:** [arXiv:2608.14643](https://arxiv.org/abs/2608.14643) · [Proof-gated-publication-PVDM](https://github.com/vaquarkhan/Proof-gated-publication-PVDM) (reference gate; not claimed identical to this production framework).

Steward keys (`SDM_VRP_HMAC_KEY`, `SDM_STEWARD_SIGN_KEY`) must live in the Steward trust domain (N2/N17), not be readable by untrusted Producer code in production.

---

## High-value additions (prioritized)

### P0 — Accuracy (do first; no new product surface)

1. Correct external report / decks: **4 phases**, not 5; SparkRules = optional.
2. Correct crypto wording: **no Merkle / no KMS Sign** unless implemented.
3. Correct SFN wording: **resume loop**, not continuation tokens.
4. Keep this due-diligence doc linked from docs index / CONTRIBUTING.

### P1 — Product value that matches the report’s strongest promises

| Addition | Why it adds value | Effort |
|----------|-------------------|--------|
| **PVDM-A schema** (decision id, agent id, prompt hash, tool call, linked VRP proof URI) | Makes “agentic governance” real without fake MCP | M |
| **MCP read-only tools** (verify_proof, trust metrics, catalog snapshot) | Grounds MCP claim; agents cannot bypass write gate | M |
| **KMS Sign option for VRP** | Makes “KMS-signed proofs” true for auditors | M |
| **PII redaction** on any agent-facing response path | Required before exposing mesh data to LLMs | M |

### P2 — DX and polish

| Addition | Why |
|----------|-----|
| `.cursorrules` (done on this branch) | Stops AI from generating Glue-ETL-as-write-path / commit-before-VRP |
| `.cursor/memory/` Memory Bank | Stable account IDs, domain list, env vars across sessions |
| Glue DQ Terraform | Only if product adopts Glue DQ (today: SparkRules + VRP) |
| Spring AI Java OTel | Separate repo; do not fold into Python framework |

### Do **not** build just because the report mentions it

- Fake “Phase 0 Integrity Gate” as a fifth PVDM phase (breaks the published pattern name).
- Glue DQ `join()` / encryption workarounds with no Glue DQ resources.
- Claiming Presidio / AgentCore / PromptGuard before MCP exists.

---

## Recommended report edits (copy-paste)

| Report text | Replace with |
|-------------|--------------|
| “Five Phases of the PVDM Lifecycle” / Phase 0 Rules | “Four phases (PVDM). Optional SparkRules DRL may run before Physical.” |
| “Merkle tree… signed using AWS KMS” | “SHA-256 multiset fingerprints; proofs signed with a veridata keypair (`VRP_SIGNING_KEY_B64`). Optional KMS for S3 SSE. KMS Sign for proofs is a hardening roadmap item.” |
| “continuation token… to the Step Function” | “IceGuard returns `rolled_back` with checkpoint offsets; Step Functions re-invokes Lambda; Durable SDK replays completed steps.” |
| Agentic / MCP / Presidio / Spring AI sections | Prefix with **“Roadmap (not shipped in aws-serverless-datamesh-framework today).”** |
| Terraform Glue DQ bugs | Move to a separate Glue DQ / platform ops note, or delete for this repo. |
| `.cursorrules` as already present | True after this branch merges; link to `.cursorrules`. |

---

## Suggested implementation sequence on this branch / follow-ups

1. **Merge accuracy docs + `.cursorrules`** (this branch).
2. Spec **PVDM-A** (`docs/roadmap-pvdm-a-agentic.md`) → schema + steward S3 layout.
3. Stub **MCP server** (read-only) gated by JWT later.
4. Optional **KMS Sign** behind feature flag.
5. Only then: Presidio / Bedrock Guardrails on agent responses.

---

## Related docs

- [Vaquar Pattern (canonical)](vaquar-pattern.md)
- [Architecture](architecture.md)
- [Observability production](observability-production.md)
- [SparkRules connector](sparkrules-connector.md)
- [Roadmap: PVDM-A / Agentic](roadmap-pvdm-a-agentic.md)
- [Cursor rules](../.cursorrules)
