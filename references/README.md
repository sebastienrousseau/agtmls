<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# references/ — shared standing docs

Cross-skill documents that many skills link to instead of restating. Unlike a
skill's own `reference.md` (deep material for *one* skill), these are reused
verbatim across the catalog.

- **`definition-of-done.md`** — the cross-skill Definition of Done. A skill's
  Verification section should link here rather than re-listing the universal
  gates; it may add stricter domain gates on top, but must not weaken it.
- **`registry-schema.md`** — generated `index.json` schema and regeneration
  rules for tool consumers.

Add a file here when a checklist or standard is referenced by more than one
skill.
