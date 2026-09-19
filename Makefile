# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT

.DEFAULT_GOAL := help
PYTHON ?= python3

.PHONY: help check test bench doctor clean build bump

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

check: ## Run the full 57-check validation suite
	$(PYTHON) scripts/run-all-checks.py

test: ## Run the unit test suite
	$(PYTHON) scripts/run-unit-tests.py

bench: ## Run behavioral and routing benchmarks
	$(PYTHON) scripts/bench.py

doctor: ## Run the agtmls-doctor health check
	$(PYTHON) scripts/agtmls-doctor.py

bump: ## Bump patch version and regenerate artifacts
	$(PYTHON) scripts/bump-version.py --version $$($(PYTHON) scripts/next-version.py)

build: ## Build wheel and sdist packages
	$(PYTHON) -m pip install --upgrade build && $(PYTHON) -m build

clean: ## Clean build and bytecode caches
	rm -rf build/ dist/ *.egg-info .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
