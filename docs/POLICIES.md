<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Support policies

## Minimum toolchain

| | Policy | Enforced by |
| :--- | :--- | :--- |
| **Python floor** | 3.10 (`requires-python = ">=3.10"`) | `pyproject.toml` |
| **Tested versions** | 3.10, 3.11, 3.12, 3.13 and 3.14 on every push to `main`; 3.10 and 3.14 on pull requests | the `checks` matrix in `.github/workflows/validate.yml` |
| **Platforms** | Ubuntu and macOS | the same matrix |
| **Runtime dependencies** | None; the standard library only | `AGENTS.md` invariant 2, and a wheel with no `Requires-Dist` |

The floor is raised only when the oldest supported version reaches upstream
end of life.

## Release line

Releases stay on `0.0.x` and move by exactly `0.0.1`; see
[`VERSIONING.md`](../VERSIONING.md). Until `1.0`, any release may change the
CLI or the registry format, and `CHANGELOG.md` marks such changes under
**Breaking**.

## Security

How to report a vulnerability, and what the analyzer does and does not
prove, is in [`SECURITY.md`](../SECURITY.md).
