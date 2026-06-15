.PHONY: install install-rules lint format test benchmark cost-estimate walkthrough demo gate-demo multi-domain dashboard init-domain version-check version-sync build clean pre-commit

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
