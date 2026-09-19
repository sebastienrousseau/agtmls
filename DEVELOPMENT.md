<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Development Guide

The single entry point for working on `agtmls`: toolchain setup, how to run every CI gate locally, test layout, and release flow.

If a gate is green here, it is green in CI.

## Contents

- [Toolchain](#toolchain)
- [Everyday commands](#everyday-commands)
- [Reproducing every CI gate](#reproducing-every-ci-gate)
- [Test layout](#test-layout)
- [Release model](#release-model)

## Toolchain

| Tool      | Version       | Purpose                                                    |
| --------- | ------------- | ---------------------------------------------------------- |
| Python    | 3.10+         | Supported runtime across Python 3.10 through 3.14.          |
| Hatchling | build backend | Zero-dependency build backend defined in `pyproject.toml`. |
| Git       | 2.30+         | Branch management, SSH-signed commits, and tagging.        |

AgtMLS is deliberately dependency-free: every utility script runs using Python stdlib alone.

## Everyday commands

```console
make test       # Run the 65 unit tests
make bench      # Run the benchmark (routing + behavioral eval checks)
make doctor     # Run agtmls-doctor health check
make check      # Run the full 57-check validation suite
```

## Reproducing every CI gate

To execute the identical suite that GitHub Actions runs on push and pull requests:

```console
python3 scripts/run-all-checks.py
```

This runs:
- `validate-skills.py`, `validate-spec-conformance.py`, `validate-licence-headers.py`
- `validate-commands.py`, `validate-plugin-manifest.py`, `validate-packaging.py`
- `validate-providers.py`, `validate-profiles.py`, `validate-templates.py`
- `validate-doc-links.py`, `validate-json-files.py`, `validate-python-scripts.py`
- `validate-shell-syntax.py`, `validate-secrets.py`, `validate-gitignore.py`
- `check-skill-collisions.py`, `run-trigger-evals.py`, `run-behavioral-evals.py`
- `run-unit-tests.py`, `bench.py`, `agtmls-doctor.py`

## Test layout

- `scripts/run-unit-tests.py`: Fast unit tests covering registry loading, manifest generation, packaging, and validation helpers.
- `evals/`: Behavioral and routing eval test cases verifying skill matching and prompt accuracy across all 30 skills.
- `scripts/bench.py`: Evaluates benchmark routing and behavioral assertions.

## Release model

AgtMLS follows a strict `0.0.x` patch-line sequencing policy (see `VERSIONING.md`). To prepare a patch release:

```console
python3 scripts/bump-version.py --version $(python3 scripts/next-version.py)
python3 scripts/release-dry-run.py --version $(python3 scripts/next-version.py)
python3 scripts/run-all-checks.py
```
