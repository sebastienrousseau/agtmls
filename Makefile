# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT

.DEFAULT_GOAL := help
PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
MANDIR ?= $(PREFIX)/share/man/man1
BASHCOMPDIR ?= $(PREFIX)/share/bash-completion/completions
ZSHCOMPDIR ?= $(PREFIX)/share/zsh/site-functions
FISHCOMPDIR ?= $(PREFIX)/share/fish/vendor_completions.d
# agtmls.py resolves its registry as Path(__file__).parent.parent, so the
# registry must be installed as a tree and the binary must be a wrapper
# pointing at it. Installing the dispatcher alone put agtmls in $(BINDIR)
# and made it look for $(PREFIX)/index.json, which never existed.
DATADIR ?= $(PREFIX)/share/agtmls
REGISTRY_DIRS := scripts skills commands agents system-prompts references templates evals
REGISTRY_FILES := index.json profiles.json providers.json lifecycle.json checks.json \
                  CATALOG.md LICENSE-APACHE LICENSE-MIT
DESTDIR ?=
PYTHON ?= python3

.PHONY: help check test bench doctor clean build bump install uninstall man completions

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

check: ## Run the full 62-check validation suite
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
	install -d $(DESTDIR)$(DATADIR)
	for d in $(REGISTRY_DIRS); do cp -R "$$d" $(DESTDIR)$(DATADIR)/; done
	for f in $(REGISTRY_FILES); do cp "$$f" $(DESTDIR)$(DATADIR)/; done
	find $(DESTDIR)$(DATADIR) -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
	install -d $(DESTDIR)$(BINDIR)
	printf '#!/bin/sh\nexec "$${PYTHON:-python3}" %s/scripts/agtmls.py "$$@"\n' '$(DATADIR)' \
	  > $(DESTDIR)$(BINDIR)/agtmls
	chmod 755 $(DESTDIR)$(BINDIR)/agtmls
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
	rm -rf $(DESTDIR)$(DATADIR)
	rm -f $(DESTDIR)$(MANDIR)/agtmls.1
	rm -f $(DESTDIR)$(BASHCOMPDIR)/agtmls
	rm -f $(DESTDIR)$(ZSHCOMPDIR)/_agtmls
	rm -f $(DESTDIR)$(FISHCOMPDIR)/agtmls.fish


