# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

**Do not open public GitHub issues for security vulnerabilities.**

Report privately to the maintainers:

1. Open a [GitHub Security Advisory](https://github.com/vaquarkhan/aws-serverless-datamesh-framework/security/advisories/new) (preferred), or
2. Email the repository owner with subject: `SECURITY: serverless-data-mesh`

Include:

- Description and impact
- Steps to reproduce
- Affected version(s)
- Suggested fix (if any)

We aim to acknowledge reports within **5 business days** and publish a fix or mitigation plan within **30 days** for confirmed issues.

## Scope

In scope:

- `serverless_data_mesh` library (coordinator, VRP gate, catalog connector)
- Example Lambda handlers and Terraform IAM policies in this repository
- Cryptographic verification and validate-then-commit bypass paths

Out of scope:

- Upstream packages (IceGuard, veridata-recon, AWS SDK): report to those projects directly
- Customer-deployed AWS account misconfiguration (overly broad IAM, public S3 buckets)

## Security model

This framework enforces **validate-then-commit**: corrupted or dropped data must not receive an Iceberg metadata commit. Security-relevant failures include:

- VRP `FAIL` not blocking metadata commit
- Proof tampering or key handling weaknesses
- Cross-account IAM that allows unauthorized catalog commits

## Hardening recommendations for deployments

- Store `VRP_SIGNING_KEY_B64` in AWS Secrets Manager; never commit keys
- Use least-privilege IAM per [docs/data-mesh-end-to-end.md](docs/data-mesh-end-to-end.md)
- Enable S3 bucket encryption and block public access (Terraform modules default to this)
- Invoke durable Lambda only via the qualified `:live` alias
- Restrict Steward proof bucket writes to Producer roles only

## Dependency updates

Automated dependency PRs are managed via Dependabot (`.github/dependabot.yml`). Review updates to `veridata-recon`, `iceguard`, and `pyiceberg` carefully: they affect the trust boundary.
