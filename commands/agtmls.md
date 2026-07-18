---
description: Run the local AgtMLS registry health check.
---

Run from the AgtMLS checkout:

```sh
python3 scripts/agtmls.py status
```

For a consumer repo, include the target agent layout:

```sh
python3 scripts/agtmls.py status --target /path/to/repo --agent codex --skills-only
```
