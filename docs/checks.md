<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# The check gate

Every check CI runs, in order. `checks.json`, `scripts/run-all-checks.py`,
and `.github/workflows/validate.yml` must agree on this list —
`validate-check-manifest.py` fails the build if they drift.

Run them all with one command:

```bash
python3 scripts/agtmls.py check
```

Or individually:

```bash
python3 scripts/validate-skills.py
python3 scripts/validate-commands.py
python3 scripts/validate-plugin-manifest.py
python3 scripts/validate-providers.py
python3 scripts/validate-profiles.py
python3 scripts/validate-templates.py
python3 scripts/validate-doc-links.py
python3 scripts/validate-json-files.py
python3 scripts/validate-python-scripts.py
python3 scripts/validate-shell-syntax.py
python3 scripts/validate-secrets.py
python3 scripts/validate-gitignore.py
python3 scripts/validate-cli-surface.py
python3 scripts/validate-system-prompts.py
python3 scripts/check-skill-collisions.py
python3 scripts/validate-eval-cases.py
python3 scripts/run-trigger-evals.py
python3 scripts/run-behavioral-evals.py
python3 scripts/validate-skill-metadata.py
python3 scripts/sync-skill-frontmatter.py --check
python3 scripts/generate-plugin-manifests.py --check
python3 scripts/generate-skill-index.py --check
python3 scripts/generate-catalog.py --check
python3 scripts/generate-docs-site.py --check
python3 scripts/validate-generated-artifacts.py
python3 scripts/validate-docs-site.py
python3 scripts/validate-skill-index.py
python3 scripts/validate-lifecycle.py
python3 scripts/validate-release.py
python3 scripts/validate-version-policy.py
python3 scripts/release-check.py
python3 scripts/smoke-release-pack.py
python3 scripts/smoke-next-version.py
python3 scripts/smoke-release-dry-run.py
python3 scripts/smoke-install.py
python3 scripts/smoke-install-profiles.py
python3 scripts/smoke-cli.py
python3 scripts/smoke-export.py
python3 scripts/smoke-import.py
python3 scripts/smoke-proposal.py
python3 scripts/smoke-scaffold.py
python3 scripts/run-unit-tests.py
python3 scripts/validate-check-manifest.py
python3 scripts/agtmls-doctor.py
```

## Optional extras

| Check | Extra | Without it |
| --- | --- | --- |
| `validate-spec-conformance.py` | `pip install skills-ref` | reports SKIP |
| `smoke-live-providers.py` | provider API keys | reports SKIP |

CI installs `skills-ref`, so spec conformance always runs on a pull request.
