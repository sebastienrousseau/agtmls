# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT

.DEFAULT_GOAL := help
PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
MANDIR ?= $(PREFIX)/share/man/man1
BASHCOMPDIR ?= $(PREFIX)/share/bash-completion/completions
ZSHCOMPDIR ?= $(PREFIX)/share/zsh/site-functions
FISHCOMPDIR ?= $(PREFIX)/share/fish/vendor_completions.d
DESTDIR ?=
PYTHON ?= python3

.PHONY: help check test bench doctor clean build bump install uninstall man completions

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

completions: ## Generate shell completions for bash, zsh, fish
	$(PYTHON) scripts/generate-completions.py --write

man: ## Generate Unix manpage (agtmls.1)
	$(PYTHON) scripts/generate-manpage.py --write

bump: ## Bump patch version and regenerate artifacts
	$(PYTHON) scripts/bump-version.py --version $$($(PYTHON) scripts/next-version.py)

build: ## Build wheel and sdist packages
	$(PYTHON) -m pip install --upgrade build && $(PYTHON) -m build

clean: ## Clean build and bytecode caches
	rm -rf build/ dist/ *.egg-info .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +

install: completions man ## Install agtmls to PREFIX (default: /usr/local)
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 scripts/agtmls.py $(DESTDIR)$(BINDIR)/agtmls
	install -d $(DESTDIR)$(MANDIR)
	install -m 644 share/man/man1/agtmls.1 $(DESTDIR)$(MANDIR)/agtmls.1
	install -d $(DESTDIR)$(BASHCOMPDIR)
	install -m 644 completions/agtmls.bash $(DESTDIR)$(BASHCOMPDIR)/agtmls
	install -d $(DESTDIR)$(ZSHCOMPDIR)
	install -m 644 completions/_agtmls $(DESTDIR)$(ZSHCOMPDIR)/_agtmls
	install -d $(DESTDIR)$(FISHCOMPDIR)
	install -m 644 completions/agtmls.fish $(DESTDIR)$(FISHCOMPDIR)/agtmls.fish

uninstall: ## Remove installed agtmls from PREFIX
	rm -f $(DESTDIR)$(BINDIR)/agtmls
	rm -f $(DESTDIR)$(MANDIR)/agtmls.1
	rm -f $(DESTDIR)$(BASHCOMPDIR)/agtmls
	rm -f $(DESTDIR)$(ZSHCOMPDIR)/_agtmls
	rm -f $(DESTDIR)$(FISHCOMPDIR)/agtmls.fish


