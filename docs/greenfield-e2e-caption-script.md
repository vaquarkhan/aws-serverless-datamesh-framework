# Greenfield E2E demo — caption script

Narration / burned-in captions for [`docs/media/greenfield-e2e-captioned.mp4`](media/greenfield-e2e-captioned.mp4).

**Product truth:** pipelines are created from **YAML/JSON metadata + `apply`**, not by drawing in the control UI. The UI observes the compiled mesh. A diagram-to-mesh designer would be a future feature.

Rebuild:

```bash
python scripts/build_greenfield_e2e_video.py
```

| # | Beat | Caption (on screen) |
|---|------|---------------------|
| 1 | Open | No diagram canvas today. Pipelines come from YAML/JSON metadata + apply — UI is for explore/trust. |
| 2 | Intent | Goal: one medallion contract expands into every layer pipeline automatically. |
| 3 | Scaffold | Edit the contract in YAML (JSON-compatible metadata). Closest “magic”: one file → many pipelines. |
| 4 | Apply | Compiler materializes bronze, silver, and gold writers + mesh orchestrator stubs. |
| 5 | Layers | Same PVDM invariant on every layer: commit_metadata ⟹ VRP = PASS. |
| 6 | UI start | UI reads generated manifests. It does not design or draw the mesh. |
| 7 | Overview | Overview: KPIs for pipelines, domains, readers readiness, VRP pass/fail, deploy-ready. |
| 8 | Pipelines | Pipelines tab: every bronze/silver/gold row the compiler emitted (handler + readers status). |
| 9 | Trust | Trust board: VRP PASS/FAIL by domain. Corrupt data never becomes Iceberg metadata. |
| 10 | PVDM | PVDM phases: Physical → Verify → Durable → Metadata. Fail-closed on VRP FAIL. |
| 11 | Durable | Dual clocks: segment timeout vs durable workload budget (resume after rolled_back). |
| 12 | Demo | Run PVDM demo locally: clean commit passes; corrupt write is blocked (no AWS required). |
| 13 | Readers + TF | Fill stubs the compiler left, build the Lambda zip, apply Terraform for the domain stack. |
| 14 | Runtime | Consumers only see proof-gated gold products — not green job logs alone. |
| 15 | Close | Docs: developer-ui-and-deploy.md · GitHub Pages embeds this captioned demo. |

## Spoken voiceover (optional, ~60–75s)

1. “You’re a greenfield developer. You need an **xyz** data product with bronze, silver, and gold — proof-gated, not just a green Glue job.”
2. “You don’t draw boxes in the UI. You scaffold a **MedallionMesh** YAML — JSON-compatible metadata — and declare domain `xyz` with all three layers.”
3. “`serverless-data-mesh apply` compiles that contract into handlers, Step Functions, VRP config, and manifests for every layer.”
4. “Open the control UI against the generated folder. Overview and Pipelines show what the compiler created. Trust and PVDM explain the gate. Durable shows the dual clocks.”
5. “Click Run PVDM demo: clean data commits; corrupt data is blocked before metadata.”
6. “Implement `readers.py`, package Lambda, `terraform apply`, then Step Functions runs IceGuard → VRP → Durable resume → Iceberg only on PASS.”
7. “That’s the end-to-end path today. A web contract editor is roadmap; a diagram designer is a separate future feature.”
