# Visual tutorial — Serverless Data Mesh (step GIFs)

Animated walkthrough of the happy path. Stills + GIFs live in [`docs/images/tutorial/`](images/tutorial/).

<p align="center">
  <img src="images/tutorial/tutorial-overview.gif" alt="Full tutorial overview GIF" width="720" />
</p>

## Steps

### 1. Install & demo
```bash
pip install serverless-data-mesh
serverless-data-mesh demo
```
![Step 1](images/tutorial/step-01-install-demo.gif)

### 2. Create mesh YAML
```bash
serverless-data-mesh new --template medallion --output my-mesh
```
![Step 2](images/tutorial/step-02-new-mesh.gif)

### 3. Apply (compile)
```bash
serverless-data-mesh apply --contract my-mesh/mesh.yaml --output my-mesh/generated
```
![Step 3](images/tutorial/step-03-apply.gif)

### 4. Open control UI
```bash
serverless-data-mesh ui --path my-mesh/generated --open
```
![Step 4](images/tutorial/step-04-ui.gif)

### 5. Package & deploy
```bash
# see examples/durable-compute for dual-clock tfvars
./infrastructure/terraform/scripts/package_lambda.sh
cd infrastructure/terraform/environments/prod && terraform apply
```
![Step 5](images/tutorial/step-05-deploy.gif)

### 6. Observe & attest
```bash
serverless-data-mesh attest demo --json
serverless-data-mesh dashboard --open
```
![Step 6](images/tutorial/step-06-observe.gif)

## Rebuild GIFs

```bash
python scripts/build_tutorial_gifs.py
```

## In-app tutorial

The mesh control UI **Tutorial** tab plays these GIFs:

```bash
serverless-data-mesh ui --path examples/medallion-e2e/generated --open
# http://127.0.0.1:8765/ → Tutorial
```
