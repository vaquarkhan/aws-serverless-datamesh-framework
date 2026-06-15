# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `SparkRulesConnector` — DRL business rules on Lambda (`[rules]` extra)
- `docs/pypi.md`, `docs/sparkrules-connector.md`, GitHub Actions `publish.yml`
- PyPI optional extras: `[rules]`, `[spark]`, `[all]`, `[publish]`
- `SDM_EXTRAS=rules` in Lambda package scripts

## [0.1.0] - 2026-06-14

### Added

- Initial release: IceGuard + Durable Execution + veridata-recon + Glue REST
- `IceGuardDurableCoordinator` for cross-domain transaction boundaries
- `GlueRestCatalogAdapter` for SigV4 Iceberg metadata commits
- `VRPProofGenerator` and `validate_then_commit` hooks
- Domain writer Lambda example with SAM template
- CI workflow, unit tests, and documentation
