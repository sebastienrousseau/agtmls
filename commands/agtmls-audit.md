---
description: Audit the registry for routing decay, spec drift, and stale artifacts.
license: MIT
---

Run the full gate, then look for what it cannot see.

```sh
python3 scripts/agtmls.py check
python3 scripts/check-skill-collisions.py
python3 scripts/agtmls.py stats
```

The gate proves data is consistent. It does not prove the catalog is *good*.
Read the ranked collision list whole: pairs climbing past 0.50 are the early
warning that two descriptions are converging.

Then check catalog balance (`stats` shows the bundle split), whether each
description says when *not* to load, and whether every `safety_policy`
matches what its skill actually instructs an agent to do.
