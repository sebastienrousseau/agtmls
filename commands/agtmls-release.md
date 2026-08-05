---
description: Walk the guarded AgtMLS release flow from version bump to published artifacts.
license: MIT
---

Releases increment by exactly `0.0.1` on the `0.0.x` line.

```sh
python3 scripts/agtmls.py next-version
python3 scripts/agtmls.py bump-version --version <next>
python3 scripts/agtmls.py check
```

`main` is protected, so land the bump through a pull request rather than
pushing directly. After it merges:

```sh
git tag -s v<next> -m "AgtMLS v<next>" && git push origin v<next>
```

Tag **before** publishing to PyPI. The release workflow builds and attests the
wheel from the tag, so publishing afterwards uploads the same artifact the
attestation covers.

Verify the chain once it is out:

```sh
gh attestation verify <wheel> --owner sebastienrousseau
```
