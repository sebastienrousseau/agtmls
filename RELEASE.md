<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Release Checklist

AgtMLS is a registry, so a release is valid only when the generated discovery
surface, plugin metadata, and validation gates agree.

1. Run `python3 scripts/bump-version.py --version $(python3 scripts/next-version.py)` to update release metadata, changelog, and generated artifacts.
2. Inspect the generated diff.
3. Regenerate the index if any manual correction was needed:

   ```sh
   python3 scripts/agtmls.py index --write
   ```

4. Run the release dry-run:

   ```sh
   python3 scripts/release-dry-run.py --version $(python3 scripts/next-version.py)
   ```

5. Run the full gate:

   ```sh
   python3 scripts/agtmls.py check
   ```

6. Inspect consumer install behavior if setup changed:

   ```sh
   python3 scripts/agtmls.py status --target /path/to/repo --agent codex --skills-only
   ```

7. Confirm `VERSIONING.md`: versions increment by exactly `0.0.1`; the next release after `v0.0.1` is `v0.0.2`, and `v0.1.0` is forbidden until `v0.0.999` exists.
8. Tag only after CI is green.

## Tagging, publishing and the audit

A pushed `v*` tag cannot be deleted or moved, so nothing is pushed until
`scripts/release-preflight.py` passes, and nothing counts as released until
`scripts/release-audit.py` reads it back from every place it was published.

1. Write the release notes in `docs/release-notes/v<version>.md`: a
   `## Summary` of user-visible changes as bullets, and a `## Checksums`
   section. A commit list is not a summary.
2. Create the signed, annotated tag on the release commit:

   ```sh
   git tag -s v<version> <commit> -m "AgtMLS v<version>"
   ```

3. Run the preflight. It checks the tag is signed by a key in `KEYS.asc`,
   titled exactly `AgtMLS v<version>`, points at `<commit>`, and that every
   packaged version at that commit is `<version>`:

   ```sh
   python3 scripts/release-preflight.py --tag v<version> --commit <commit> \
       --notes docs/release-notes/v<version>.md --pending-checksums
   ```

   The artifacts are built by `release.yml` after the tag is pushed, and the
   build is not byte-reproducible, so their checksums cannot exist before the
   push. The notes' Checksums section says `pending` and the preflight runs
   with `--pending-checksums`. This is a standing deviation from the
   "checksums before push" rule in AGENTS.md, closed in step 4 instead:
   nothing is visible or publishable until the real checksums are checked.
   Reproducible builds would remove it.
4. Push the tag. `release.yml` then, in order:
   - waits for your approval of the `release` environment, then signs the
     exact bytes of `index.json` with the release key (agtmls-spec chapter
     9) and verifies the signature against the tag's `ALLOWED_SIGNERS`. The
     environment deploys only from `v0.0.*` tags, so a manual re-release
     dispatched from a branch cannot sign, and publishes unsigned;
   - builds once, with `index.json.sig` beside `index.json` in the wheel,
     and writes one `SHA256SUMS` over every asset, wheel, sdist and
     `index.json.sig` included; the installed wheel's signature is verified
     before anything is attached;
   - writes the release body with `scripts/release-body.py`: the prepared
     notes, their Checksums section replaced by that `SHA256SUMS`;
   - attaches the assets to a **draft** release, and refuses to publish it
     unless GitHub holds every one;
   - publishes the release and runs `scripts/release-audit.py --before-pypi`;
   - stops at the `pypi` environment, which needs a maintainer's approval.
     The publish job uploads the build job's files, never a rebuild.
5. Approve the `pypi` deployment, then run the audit in full. For any tag
   whose commit has `ALLOWED_SIGNERS`, the audit also requires an
   `index.json.sig` asset that verifies against it:

   ```sh
   python3 scripts/release-audit.py --tag v<version> --commit <commit>
   ```

   The release is done when it passes.

To re-release an existing tag whose release was left incomplete, dispatch the
workflow with that tag and `dry_run: false`. It reuses the release only if it
has no assets; it never replaces a release that shipped.

## Tag protection

Treat published `v*` tags as immutable. See `docs/tag-protection.md`. Repository settings should protect `v*` tags from deletion or force-push where GitHub tag protection/rulesets are available.
