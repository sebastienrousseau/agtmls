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
make check      # Run the full 62-check validation suite
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

## Regenerating the SBOM after a commit

`SBOM.spdx.json` and `provenance.json` take their timestamp from the commit
that last changed a path they describe. That is deliberate: the previous
generator hardcoded `1970-01-01T00:00:00Z` to satisfy the determinism gate,
which made the field deterministic by making it false.

The consequence is an ordering requirement. A commit that touches `scripts/`,
`skills/`, `index.json` or any other covered path moves the timestamp, so the
gate will report the SBOM stale immediately afterwards:

```bash
git commit -m 'fix(scripts): ...'        # gate now reports a stale SBOM
python3 scripts/generate-sbom.py --write
python3 scripts/generate-provenance.py --write
git commit SBOM.spdx.json SBOM.cyclonedx.json provenance.json \
  -m 'chore: regenerate supply-chain artifacts'
```

The regeneration commit must contain **only** generated files. Mixing an
authored change into it moves the timestamp again and you go round once more.

This converges in exactly one step, and `scripts/_lib/covered.py` is why: both
generators take their date from **authored** paths only, never from a generated
artifact. Committing the regenerated files cannot move a timestamp derived from
files they are not.

Getting that wrong is easy and was got wrong here first: provenance originally
timestamped itself from its own materials, which include `SBOM.spdx.json`, so
committing a regenerated SBOM invalidated provenance and the pair never
settled. If a new path joins `SOURCE_DIRS` or `SOURCE_FILES`, check it is
authored rather than generated.
