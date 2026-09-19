<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Publishing the ecosystem

Every release workflow is written and uses **Trusted Publishing**, so no
long-lived token exists in any repository or any GitHub secret. That is the
point: a token that does not exist cannot leak, be committed, or be stolen
from a workflow run.

The cost is a one-time registration per package, done in a browser. It cannot
be scripted, and nothing publishes until it is done.

## What is already true

| Package | Registry | Workflow | Job environment |
| :--- | :--- | :--- | :--- |
| `agtmls` | PyPI | `agtmls/.github/workflows/release.yml` | `pypi` |
| `agtmls-core`, `agtmls-cli` | crates.io | `agtmls-core/.github/workflows/release.yml` | `crates-io` |
| `@agtmls/wasm` | npmjs | `agtmls-wasm/.github/workflows/release.yml` | `npm` |

Each job already declares `permissions: id-token: write`, which is what mints
the OIDC identity the registry exchanges for a short-lived token.

## One-time setup

### 1. Create the GitHub environment

For each repository above: **Settings → Environments → New environment**, named
exactly as the table says. Add yourself as a **required reviewer**.

The reviewer gate is the part worth not skipping. Trusted Publishing means any
workflow run on that repository which reaches the publish job can publish; the
environment is what puts a human between a merged pull request and the
registry.

### 2. Register the trusted publisher

**PyPI** — pypi.org → *Your projects* → `agtmls` → *Publishing* → *Add a new
publisher* → GitHub:

```
Owner:        sebastienrousseau
Repository:   agtmls
Workflow:     release.yml
Environment:  pypi
```

**crates.io** — crates.io → `agtmls-core` → *Settings* → *Trusted Publishing*.
Repeat for `agtmls-cli`; each crate is registered separately.

```
Repository:   sebastienrousseau/agtmls-core
Workflow:     release.yml
Environment:  crates-io
```

**npmjs** — npmjs.com → `@agtmls/wasm` → *Settings* → *Trusted publisher*.

```
Repository:   sebastienrousseau/agtmls-wasm
Workflow:     release.yml
Environment:  npm
```

For a package that does not exist yet, npm and PyPI both accept a *pending*
publisher, registered before the first release. crates.io requires the crate to
exist, so the first `agtmls-core` publish needs a token; delete it afterwards.

### 3. Rehearse before releasing

Every workflow takes a `dry_run` input, defaulting to true:

```bash
gh workflow run release.yml --repo sebastienrousseau/agtmls-wasm -f dry_run=true
```

A dry run builds, validates and runs `npm publish --dry-run` or the equivalent.
It proves the pipeline without putting anything on a registry.

### 4. Release

```bash
git tag -s v0.0.7 -m "v0.0.7"
git push origin v0.0.7
```

The tag is the trigger. Each workflow checks the tag against the version in the
repository and refuses if they disagree, so a mistyped tag fails before it
publishes rather than after.

## Order matters once

`agtmls-cli` depends on `agtmls-core` by exact version, so the core must be on
the index before the CLI can resolve it. The workflow publishes them in that
order with a pause between; nothing else in the ecosystem has a publish-order
constraint.

`agtmls-wasm` and `agtmls-mcp` depend on `agtmls-core` by **pinned git
revision** until it is on crates.io. After the first crates.io release, change
both to a version pin — a git dependency is reproducible but it is not
something a downstream consumer can audit as easily as a registry version.

## Checking your work

```bash
python3 scripts/check-publishing-readiness.py
```

It reports, per package, whether the workflow exists, whether it declares
`id-token: write`, and whether the environment name matches what the registry
will be told. It cannot see the registry side — that is the part you confirm in
the browser.
