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

Or individually, in the order the gate runs them:

<!-- generated:checks source="checks.json" -->
```bash
python3 scripts/validate-skills.py
python3 scripts/validate-spec-conformance.py
python3 scripts/validate-licence-headers.py
python3 scripts/validate-commands.py
python3 scripts/validate-plugin-manifest.py
python3 scripts/validate-packaging.py
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
python3 scripts/sync-spec-rules.py --check
python3 scripts/validate-security-claims.py
python3 scripts/run-security-evals.py
python3 scripts/audit-skill.py --all --strict
python3 scripts/run-trigger-evals.py
python3 scripts/run-behavioral-evals.py
python3 scripts/validate-skill-metadata.py
python3 scripts/sync-skill-frontmatter.py --check
python3 scripts/generate-plugin-manifests.py --check
python3 scripts/generate-skill-index.py --check
python3 scripts/generate-catalog.py --check
python3 scripts/generate-docs-site.py --check
python3 scripts/generate-mcp-resources.py --check
python3 scripts/generate-benchmarks-doc.py --check
python3 scripts/generate-checks-doc.py --check
python3 scripts/generate-sbom.py --check
python3 scripts/validate-sbom-conformance.py
python3 scripts/generate-provenance.py --check
python3 scripts/validate-generated-artifacts.py
python3 scripts/validate-docs-site.py
python3 scripts/validate-governance.py
python3 scripts/validate-skill-index.py
python3 scripts/validate-lifecycle.py
python3 scripts/validate-version-policy.py
python3 scripts/validate-release.py
python3 scripts/release-check.py
python3 scripts/smoke-release-pack.py
python3 scripts/smoke-next-version.py
python3 scripts/smoke-bump-version-check.py
python3 scripts/smoke-release-dry-run.py
python3 scripts/smoke-evolve-evidence.py
python3 scripts/smoke-provider-install.py
python3 scripts/smoke-live-providers.py
python3 scripts/smoke-install.py
python3 scripts/smoke-install-safety.py
python3 scripts/smoke-install-verify.py
python3 scripts/smoke-install-profiles.py
python3 scripts/smoke-cli.py
python3 scripts/smoke-offline.py
python3 scripts/smoke-make-install.py
python3 scripts/smoke-export.py
python3 scripts/smoke-import.py
python3 scripts/smoke-proposal.py
python3 scripts/smoke-scaffold.py
python3 scripts/run-unit-tests.py
python3 scripts/bench.py --smoke
python3 scripts/validate-check-manifest.py
python3 scripts/agtmls-doctor.py --skip-gate
```
<!-- /generated:checks -->

## Optional extras

| Check | Extra | Without it |
| --- | --- | --- |
| `validate-spec-conformance.py` | `pip install skills-ref` | reports SKIP |
| `smoke-live-providers.py` | provider API keys | reports SKIP |

CI installs `skills-ref`, so spec conformance always runs on a pull request.
