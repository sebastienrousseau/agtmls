<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Security Policy

AgtMLS ships agent-facing instructions. Treat those instructions as executable
influence: a bad skill can steer an agent into unsafe commands, data leakage, or
incorrect public claims.

## Reporting

Report security issues privately to the maintainer before publishing details.
Include the affected file, expected impact, and a minimal reproduction where
possible.

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
