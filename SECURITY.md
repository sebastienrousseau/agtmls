<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Security Policy

AgtMLS ships agent-facing instructions. Treat those instructions as executable
influence: a bad skill can steer an agent into unsafe commands, data leakage, or
incorrect public claims.

## Reporting

Report privately through
[GitHub Security Advisories](https://github.com/sebastienrousseau/agtmls/security/advisories/new),
which opens a channel only you and the maintainer can read. Do not open a
public issue for a vulnerability, and do not publish details before a fix is
available.

Include the affected file, the expected impact, and a minimal reproduction
where possible. A skill that steers an agent into unsafe commands is in scope
even when it runs no code itself.

### Response window

AgtMLS is maintained by one person, so these are the commitments that can be
kept rather than the ones that sound best:

| Stage | Target |
| :--- | :--- |
| Acknowledgement | within 5 business days |
| Initial assessment, with a severity and a direction | within 10 business days |
| Fix or documented mitigation for HIGH and CRITICAL | within 30 days of assessment |
| Public advisory | with the release that carries the fix |

If an acknowledgement has not arrived within 5 business days, the report has
been missed rather than declined; escalate by opening a public issue that says
a private report is outstanding, without the details.

## Boundaries and heuristics

A boundary holds regardless of what a skill says; a heuristic is best-effort
and can be evaded. Knowing which is which is the point of this section.

| Protection | Kind | What it establishes |
| :--- | :--- | :--- |
| `integrity` digest per skill in `index.json` | Boundary | The installed files are byte-for-byte the files this registry published |
| `install` verifying the source before copying (exit `3`) | Boundary | A tampered registry is refused before anything reaches your repository |
| `verify` against `.agtmls/manifest.json` | Boundary | Drift after install — modified, missing or unmanaged files — is reported |
| Signed commits and tags (`KEYS.asc`) | Boundary | Which maintainer key produced a given revision |
| `agtmls audit` rules (`AGT-STEG`, `AGT-INJ`, `AGT-EXEC`, `AGT-EXFIL`) | Heuristic | Known patterns are flagged on the text an agent reads (hidden code points stripped, NFKC-folded); packed or obfuscated payloads can evade static scanning. In-source suppressions need a reason and never cover `AGT-STEG` |
| Capability and policy honesty (`AGT-CAP`, `AGT-POLICY`) | Heuristic | Frontmatter and `metadata.json` agree with each other and with the skill's prose; it cannot see what a script does at run time |
| Collision, routing and behavioral evals | Heuristic | Skills stay distinguishable and keep their documented shape; they do not measure whether a skill helps |

Not provided, today: execution sandboxing, runtime detonation of untrusted
skills, and a signature over `index.json` that proves who published it. The
digest proves a skill matches the index; it does not yet prove the index came
from this project. Until it does, obtain the registry from this repository or
from PyPI directly, not from a mirror.

## Security rules for skills

- Do not hardcode API keys, tokens, passwords, cookies, or private endpoints.
- Do not ask agents to exfiltrate local files, secrets, browser state, or
  credentials.
- Do not add destructive shell actions without an explicit user-approval step.
- Prefer dry-run, doctor, status, and verification commands before mutation.
- Keep dual-use security material scoped to authorized, lawful work only.
- Keep provenance commands local and auditable; cite external claims that drift.

## Session and telemetry policy

This repo has no background runtime session capture. The explicit proposal
tool, `scripts/propose-skill-from-session.py`, only reads a transcript file the
operator provides, redacts likely secrets, writes a local draft under
`.agtmls/proposals/`, and never publishes or installs the result. Future
loop/evolution components must keep those same defaults unless a maintainer
adds a reviewed policy and implementation.
