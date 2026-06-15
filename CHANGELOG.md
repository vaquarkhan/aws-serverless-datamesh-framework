# Changelog

All notable changes to this project will be documented in this file.

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
