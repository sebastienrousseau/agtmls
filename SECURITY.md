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
