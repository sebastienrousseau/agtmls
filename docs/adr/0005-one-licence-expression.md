<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0005. One licence expression, read from pyproject.toml

- **Status:** accepted
- **Date:** 2026-11-16

## Context

AgtMLS is offered under `Apache-2.0 OR MIT`, and the maintainer requires
it to stay that way. Until v0.0.31, 126 files carried MIT-only or
`MIT OR Apache-2.0` SPDX headers. All 33 skills said `license: MIT`, and
so did the plugin manifests, the marketplace and `index.json`, because
two generators defaulted to `"MIT"` and the manifest check required it.
A label that names MIT alone tells a reader that the Apache-2.0 grant,
and its patent licence, does not cover that file.

Skill frontmatter cannot carry a comment header, so a skill states its
licence in the Agent Skills `license` field. The format leaves that field
as free text, and the reference validator (`skills-ref` 0.1.1) accepts
any string there: `validate-spec-conformance.py` passes all 33 skills
labelled `Apache-2.0 OR MIT`.

## Decision

`pyproject.toml`'s `license = "Apache-2.0 OR MIT"` is the one place the
expression is written by hand. `scripts/_lib/licence.py` reads it, and
everything that writes a label (skill frontmatter, `index.json`) takes it
from there. Every label uses that exact spelling, so one grep finds every
file.

Two gate checks enforce it. `validate-licence-headers.py` requires the
expression in every SPDX header (Markdown, Python, shell, YAML, TOML) and
in every frontmatter `license:` line. `validate-licence-consistency.py`
compares every JSON licence label, the CycloneDX expression and
`CITATION.cff` with it.

Two things are not labels and are left as they are: recorded agent runs
under `docs/evidence/`, which quote what a fixture said at the time, and
the SPDX document's `dataLicense`, which the SPDX spec fixes at
`CC0-1.0`. Third-party text is never pasted into the registry. Ideas taken
from other projects are rewritten and credited in `CREDITS.md`, so no
file carries a licence other than the project's.

## Consequences

Changing the licence is a one-line edit followed by each generator's
`--write`; a missed label fails the gate. A skill can no longer carry
its own licence. A skill imported from elsewhere under another licence
cannot ship in the registry as it is: it has to be rewritten, or kept
out. Relabelling a skill changes its digest, so a `hardened` skill needs
a new uplift run after it, as `vetting-a-skill-before-install` did in
v0.0.31.
