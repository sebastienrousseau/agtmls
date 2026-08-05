---
description: Scaffold a new AgtMLS skill with its metadata and both eval cases.
license: MIT
---

Scaffold a skill, then author it against the contract.

```sh
python3 scripts/agtmls.py scaffold-skill <name>
python3 scripts/agtmls.py scaffold-skill <name> --bundle <bundle>
```

That writes `skills/<name>/` with `SKILL.md`, `reference.md`,
`metadata.json`, and both eval cases.

Write the description first — it is the entire routing surface, and the
tokenizer does not stem, so use the exact word forms a user would type. Then:

```sh
python3 scripts/sync-skill-frontmatter.py --write
python3 scripts/generate-skill-index.py --write
python3 scripts/agtmls.py check
```
