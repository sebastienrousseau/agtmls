# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# GNU make reads this file before Makefile. Makefile stays portable to any
# POSIX make; under GNU make it is included whole, plus the targets the GNU
# Coding Standards (section 7.2.3) expect of a package that installs:
# all, installcheck, distclean and dist.

include Makefile

.PHONY: all installcheck distclean dist

all: completions man ## Build what install installs: completions and the manpage

installcheck: ## Run the installed agtmls; use after make install, same PREFIX and DESTDIR
	"$(DESTDIR)$(BINDIR)/agtmls" --version
	"$(DESTDIR)$(BINDIR)/agtmls" stats --json >/dev/null
	test -f "$(DESTDIR)$(MANDIR)/agtmls.1"

distclean: clean ## Remove everything clean does; nothing is configured, so nothing more

dist: build ## Build the source and wheel distributions
