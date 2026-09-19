# Developer guide: local control UI → create mesh → Terraform deploy

**Audience:** developers and platform engineers testing Serverless Data Mesh locally, then deploying to AWS.

This is the honest product path:

```text
Design Studio (region·accounts·VPC) or YAML contract
       →  apply/compile  →  local control UI (observe + Design)
       →  implement readers.py  →  package Lambda  →  terraform apply  →  Step Functions run
```

- **Not Jetty / Tomcat / Node.** The control UI is Python’s stdlib `ThreadingHTTPServer`.
- **Design Studio** writes `mesh.yaml` and can run apply into `generated/`; you can still author YAML by hand.

---

## 0. Prerequisites

| Tool | Why |
|------|-----|
| Python **3.12+** | Package + UI + local demos |
| Git clone of this repo | Northstar sample + Terraform modules |
| (Deploy) AWS CLI, Terraform ≥ 1.5 | Prod stack |
| (Deploy) Docker optional | Linux Lambda zip packaging |

```bash
# Windows PowerShell
cd path\to\aws-serverless-datamesh-framework
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

```bash
# macOS / Linux
cd path/to/aws-serverless-datamesh-framework
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Quick check (no AWS):

```bash
serverless-data-mesh demo
```

---

## 1. How the control UI starts

CLI entry: `serverless-data-mesh ui` → `serverless_data_mesh.ui.server.serve_ui()`.

| Detail | Value |
|--------|--------|
| Server | `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` |
| Default bind | `127.0.0.1:8765` |
| Static assets | `src/serverless_data_mesh/ui/static/` (`index.html`, `app.js`, `app.css`) |
| Dashboard data | Reads your **generated** mesh folder (`mesh.manifest.json`, pipelines, proofs) |
| Browser | `--open` calls `webbrowser.open` |

```bash
serverless-data-mesh ui --path examples/medallion-e2e/generated --host 127.0.0.1 --port 8765 --open
```

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:8765/ | Control center (Overview / Pipelines / Trust / PVDM / Durable / Tutorial) |
| http://127.0.0.1:8765/walkthrough | Auto-play GIF demo |
| http://127.0.0.1:8765/api/dashboard | JSON dashboard payload |

**Header actions:** Demo walkthrough · Refresh · Run PVDM demo · Attest demo.

Stop the server with `Ctrl+C` in the terminal.

### Control UI demo videos

| Video | What it shows |
|-------|----------------|
| [`greenfield-e2e-captioned.mp4`](media/greenfield-e2e-captioned.mp4) | Captioned greenfield → XYZ medallion → apply → UI → Terraform |
| [`control-ui-final.mp4`](media/control-ui-final.mp4) | Live Design Studio: region · accounts · VPC → domains → pipelines |
| Caption script | [`greenfield-e2e-caption-script.md`](greenfield-e2e-caption-script.md) |

Rebuild greenfield: `python scripts/build_greenfield_e2e_video.py`  
Rebuild Control UI final: `python scripts/build_final_ui_video.py` (needs UI on `:8765` + Playwright)

Site embed: [GitHub Pages landing](https://vaquarkhan.github.io/aws-serverless-datamesh-framework/)

---

## 2. Create workflow (pipelines from YAML)

### Step A — Scaffold or use the sample

```bash
# Option 1: your own mesh
serverless-data-mesh new --template medallion --output my-mesh
# edit my-mesh/mesh.yaml

# Option 2: northstar sample (orders + payments → 6 pipelines)
# use examples/medallion-e2e/northstar.mesh.yaml
```

### Step B — Compile

```bash
serverless-data-mesh apply `
  --contract examples/medallion-e2e/northstar.mesh.yaml `
  --output examples/medallion-e2e/generated
```

(`apply` = validate → compile → doctor → `GETTING_STARTED.md`.)

### Step C — Open the UI (observe only)

```bash
serverless-data-mesh ui --path examples/medallion-e2e/generated --open
```

Confirm under **Pipelines** that bronze / silver / gold rows appear. The UI did not create them — `apply` did.

### Step D — Implement I/O

```bash
serverless-data-mesh doctor --path examples/medallion-e2e/generated
```

Fill each layer’s `readers.py` (source/sink). Re-run `apply` after YAML edits.

### Step E — Optional local proofs

In the UI: **Run PVDM demo** / **Attest demo**, or:

```bash
serverless-data-mesh demo
serverless-data-mesh attest demo --json
```

---

## 3. Package + Terraform deploy

Full prod checklist: [aws-production-deploy.md](aws-production-deploy.md) · knobs: [terraform-guide.md](terraform-guide.md).

### Package Lambda (Linux-compatible zip)

```bash
# Git Bash / WSL / Linux
./infrastructure/terraform/scripts/package_lambda.sh
```

Point `lambda_package_path` at the zip. Handler for the platform demo is typically:

`examples.domain_writer.handler.lambda_handler`

Compiled domain layers use flat `handler.lambda_handler` at zip root — see generated `layer_lambda.manifest.json`.

### Terraform (prod example)

```bash
cd infrastructure/terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
# edit: unique bucket names, domain_id, glue names, timeouts

terraform init
terraform plan
terraform apply
```

Key variables:

| Variable | Meaning |
|----------|---------|
| `lambda_timeout_seconds` | Segment clock (≤900 on-demand; ≤5400 with LMI) |
| `durable_execution_timeout_seconds` | Total job budget |
| `sfn_lambda_invoke_mode` | `sync` (AWS ≤15 min) or `async_callback` (LMI ≤90 min) |
| `enable_lambda_managed_instances` | Opt-in LMI + capacity provider ARN |
| `lambda_subnet_ids` / `lambda_security_group_ids` | Used when `vpc_mode=existing` |
| `vpc_mode` | `none` (default) · `existing` · `create` |
| `vpc_cidr_block` / `vpc_az_count` | Used when `vpc_mode=create` |

### VPC & IAM (defaults — honest answers)

| Topic | Default | Notes |
|-------|---------|--------|
| **VPC** | **`none`** | Lambdas are **not** in your account default VPC. `none` = AWS-managed network. **`existing`** = your subnet/SG IDs. **`create`** = Terraform module `vpc-lambda` builds a private VPC + Lambda SG. |
| **IAM** | **Terraform-created** | `{name_prefix}-domain-writer` (+ Step Functions / EventBridge). Design UI asks for **account IDs + region + VPC mode** — never role ARNs. |
| **Accounts** | Single or three | Design → Create data mesh: single-account (POC) or Producer · Steward · Publisher. |

Design Studio **Create data mesh** writes region, accounts, and networking into `mesh.yaml` + `terraform.contract.txt`.

### First run

```bash
# from terraform outputs
aws stepfunctions start-execution `
  --state-machine-arn "$(terraform output -raw step_functions_arn)" `
  --input file://payload.json
```

Prefer SFN over bare `lambda invoke` for production resume loops.

---

## 4. After deploy — observe

| Signal | Where |
|--------|--------|
| Structured outcomes | CloudWatch Logs → `event = "pvdm_outcome"` |
| Trust metrics | Namespace `ServerlessDataMesh/Trust` |
| SNS | Confirm email/HTTPS subscription after apply |
| DLQ | Async hard failures |
| Control UI | Still local against **generated** artifacts (not live AWS unless you point proofs/dirs accordingly) |

Smoke scripts: see [observability-production.md](observability-production.md).

---

## 5. GitHub Pages (this site)

Static files under `docs/` are published by [`.github/workflows/pages.yml`](../.github/workflows/pages.yml).

| Page | URL (after Pages is enabled) |
|------|------------------------------|
| Landing | `https://vaquarkhan.github.io/aws-serverless-datamesh-framework/` |
| Walkthrough | `.../demo-walkthrough.html` |

**One-time repo setup:** GitHub → **Settings → Pages → Source: GitHub Actions** (then push to `main` or run the workflow manually).

The Pages site documents and demos; it does **not** replace the local control UI.

---

## 6. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: serverless_data_mesh` | `pip install -e .` from repo root (activated venv) |
| UI shows 0 pipelines | Run `apply` first; pass the correct `--path` to `ui` |
| Port in use | `--port 8766` or stop the other process |
| Windows line breaks in docs | Use `` ` `` (PowerShell) or `\` (bash), not bash-only heredocs |
| Sync SFN + `lambda_timeout > 900` | Set `sfn_lambda_invoke_mode=async_callback` + LMI |

---

## Related

- [how-to-start.md](how-to-start.md) — GIF steps
- [metadata-driven-pipeline.md](metadata-driven-pipeline.md) — YAML schema
- [first-mesh-on-aws.md](first-mesh-on-aws.md) — short AWS path
- [architecture.md](architecture.md) — PVDM + durable clocks
