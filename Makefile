.PHONY: install install-rules lint format test benchmark cost-estimate walkthrough demo gate-demo multi-domain dashboard init-domain version-check version-sync build clean pre-commit mesh-new mesh-apply mesh-doctor mesh-validate

install:
	pip install -e ".[dev]"
	pip install veridata-recon

install-rules:
	pip install -e ".[rules,dev]"
	pip install veridata-recon

lint:
	ruff check src tests examples eval scripts
	ruff format --check src tests examples eval scripts

format:
	ruff format src tests examples eval scripts
	ruff check --fix src tests examples eval scripts

test:
	pytest tests/ -v

benchmark:
	python eval/validate_then_commit_benchmark.py

cost-estimate:
	python benchmarks/run_cost_estimate.py --write

walkthrough:
	python examples/tutorials/walkthrough.py

demo:
	serverless-data-mesh demo

gate-demo:
	python examples/tutorials/verification_gate_demo.py

multi-domain:
	python examples/multi-domain-orders-payments/test_atomicity.py

dashboard:
	serverless-data-mesh dashboard --open

mesh-new:
	serverless-data-mesh new --template medallion --output my-mesh

mesh-apply:
	serverless-data-mesh apply --contract my-mesh/mesh.yaml --output my-mesh/generated

mesh-doctor:
	serverless-data-mesh doctor --path my-mesh/generated

mesh-validate:
	serverless-data-mesh validate --contract my-mesh/mesh.yaml

mesh-northstar:
	serverless-data-mesh apply --contract examples/medallion-e2e/northstar.mesh.yaml --output examples/medallion-e2e/generated

mesh-deploy:
	serverless-data-mesh deploy --contract my-mesh/mesh.yaml --output my-mesh/generated --dry-run

mesh-ui:
	serverless-data-mesh ui --path my-mesh/generated --open

mesh-catalog:
	serverless-data-mesh catalog export --contract my-mesh/mesh.yaml --output integrations/backstage/entities

benchmark-local:
	python benchmarks/run_local_benchmark.py

version-check:
	python scripts/sync_version.py --check

version-sync:
	python scripts/sync_version.py --write

pre-commit:
	pip install pre-commit
	pre-commit install
	pre-commit run --all-files

build:
	python -m build

clean:
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

sam-build:
	sam build -t infrastructure/sam/template.yaml

tf-package:
	./infrastructure/terraform/scripts/package_lambda.sh

tf-plan:
	cd infrastructure/terraform/environments/prod && terraform plan

tf-apply:
	cd infrastructure/terraform/environments/prod && terraform apply
