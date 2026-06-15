.PHONY: install lint format test build clean

install:
	pip install -e ".[dev]"
	pip install veridata-recon

install-rules:
	pip install -e ".[rules,dev]"
	pip install veridata-recon

lint:
	ruff check src tests examples
	ruff format --check src tests examples

format:
	ruff format src tests examples
	ruff check --fix src tests examples

test:
	pytest tests/ -v

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
