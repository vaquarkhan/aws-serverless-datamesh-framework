# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.0.0] - 2026-06-14

Production release: metadata-driven medallion mesh, zero-friction CLI, and Terraform deploy path.

### Added

- **Metadata-driven pipeline compiler** (`serverless-data-mesh compile`)
- `sdm/v1` `DataProductPipeline` and `MedallionMesh` YAML contract models
- Generated artifacts: handler, readers stub, pipeline_config, Step Functions, EventBridge, tests
- `serverless_data_mesh.compile.runtime.run_metadata_pipeline`
- Example contract: `examples/contracts/payments.mesh.pipeline.yaml`
- **Real-world retail ETL walkthrough**: `examples/retail-mesh/` (5 pipelines, PySpark on Lambda)
- **Medallion E2E mesh**: `examples/medallion-e2e/` — one YAML → bronze/silver/gold for all domains
- **Complete metadata guide**: `docs/metadata-driven-pipeline.md` — full schema, deploy, CI/CD
- **Zero-friction CLI**: `new`, `apply`, `validate`, `doctor` — YAML to full mesh in 2 commands
- **Terraform medallion-mesh module** and `environments/medallion/` stack
- Prod stack: mesh trust dashboard domains, optional Lake Formation governance module
- Dependency: `pyyaml>=6`

### Changed

- `serverless-data-mesh init` now uses the compile pipeline (outputs `mesh.pipeline.yaml`)
- PyPI classifier: **Production/Stable**

## [0.2.0] - 2026-06-15

### Added

- **Auto VRP reprocessing** (`orchestration/reprocess.py`): detect drops, repair sink, re-proof, commit or escalate
- **Consumer SLA enforcement** (`governance/consumer_sla.py`): freshness, completeness, required columns; LF grant hook
- **Live CloudWatch trust dashboard** (Terraform `monitoring/dashboard.tf` + `publish_vrp_metric`)
- **Grafana template** (`infrastructure/grafana/mesh-trust-dashboard.json`)
- **Lake Formation governance module** (`terraform/modules/governance/`)
- CLI: `serverless-data-mesh canary`, `reprocess-demo`, `dashboard --cloudwatch`
- Scaffold: `consumer_sla.yaml`, `step_function.asl.json`, richer handler imports
- Docs: `docs/mesh-trust-dashboard.md`
- Tests: reprocess, consumer SLA, canary, auto-repair demo

### Changed

- `IceGuardDurableCoordinator` supports optional `sink_reader` + `enable_auto_repair`
- Trust dashboard supports proofs scan, CloudWatch live mode, and demo fallback

## [0.1.3] - 2026-06-15

### Added

- **Pure-Python fallback verifier** when veridata-recon wheels unavailable (Windows/Mac demo works)
- `serverless-data-mesh init` domain scaffold CLI
- `serverless-data-mesh dashboard` mesh trust dashboard HTML
- `benchmarks/run_cost_estimate.py` with published cost estimates (100K/1M/10M)
- `ConsumerSLAContract` type and `run_canary_comparison` for progressive delivery
- Tests: fallback verifier, scaffold, dashboard

### Changed

- Local demo, gate demo, multi-domain, and benchmark use `create_proof_generator()` auto-backend
- `benchmarks/results/2026-06-baseline.json` populated (pricing model estimated)

## [0.1.2] - 2026-06-15

### Added

- **Local demo**: `serverless-data-mesh demo` runs PVDM in <60s without AWS (`LocalPVDMRuntime`)
- `examples/tutorials/verification_gate_demo.py`: corrupt data blocked before consumers
- `examples/multi-domain-orders-payments/`: deferred mesh leader commit + `test_atomicity.py`
- `benchmarks/`: cost comparison methodology, workloads (100k/1M/10M), results placeholder
- `serverless_data_mesh.lineage`: OpenLineage `emit_openlineage_event` on commit
- Tests: `test_local_runtime.py`, `test_openlineage.py`

## [0.1.1] - 2026-06-15

### Added

- **Vaquar Pattern** (`docs/vaquar-pattern.md`): proof-gated serverless lakehouse publication (PVDM)
- Blog-style [why-serverless-data-mesh.md](docs/why-serverless-data-mesh.md) with connectivity diagrams
- New diagram assets: `why-sdm-hero-connectivity.png`, `why-sdm-four-phase-connectivity.png`, `why-sdm-trust-gap.png`

### Fixed

- Hatch `VERSION` parsing: `pattern` for plain semver file (CI build green)
- `__version__` reads from package metadata when installed; dev fallback uses `parents[2]`
- Multi-account Terraform: Steward creates only checkpoint/proof buckets; Publisher creates only lakehouse
- Storage module: optional per-bucket creation via nullable bucket names

### Changed

- Pattern catalog: Vaquar Pattern as flagship pattern #0 in [data-mesh-patterns.md](docs/data-mesh-patterns.md)

## [0.1.0] - 2026-06-14

### Added

- Initial release: IceGuard + Durable Execution + veridata-recon + Glue REST
- `IceGuardDurableCoordinator` for cross-domain transaction boundaries
- `GlueRestCatalogAdapter` for SigV4 Iceberg metadata commits
- `VRPProofGenerator` and `validate_then_commit` hooks
- Domain writer Lambda example with SAM template
- `VERSION` file, pre-commit, Dependabot, SECURITY.md, consumer safety benchmark
- `SparkRulesConnector` (`[rules]` extra), PyPI publish workflow
- CI workflow, unit tests, and documentation
