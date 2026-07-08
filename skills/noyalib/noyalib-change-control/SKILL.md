---
name: noyalib-change-control
description: |
  Load this when working on the noyalib repo and you need to classify a change,
  decide which gates it must pass, prepare a PR, answer "am I allowed to do X?",
  decide whether you may bump the MSRV (a breaking event needing an ADR), or judge
  release readiness. Covers change taxonomy (bug fix / feature / security /
  restructure / release), the written non-negotiables (forbid(unsafe_code), signed
  Conventional Commits, ADR triggers, panic policy, MSRV, CI-always-green), the
  unwritten project laws confirmed with the maintainer, the v0.0.9→v0.0.11 CI
  cache-poisoning incident behind the isolated CARGO_TARGET_DIR rule, and the PR
  review flow. Siblings: noyalib-ci-and-release (HOW to run gates locally) and
  noyalib-validation-and-qa (WHAT evidence a change needs) — this is the rulebook,
  not the runbook. Date-stamped 2026-07-08; release branch feat/v0.0.14.
---

# noyalib — Change control rulebook

> **Reference material** (full 9-row change taxonomy, complete CI gate
> inventory, long-form v0.0.9 → v0.0.11 cache-poisoning narrative,
> jargon glossary): see `reference.md` in this directory. Load when you
> need the exhaustive table for §1, the gate-name inventory that fills
> in §5, or the incident write-up that §4 summarises.

Repo: `github.com/sebastienrousseau/noyalib` — pure-Rust YAML 1.2 library,
zero `unsafe`, release branch `feat/v0.0.14`. Ground truth: `PLAN.md`
(§ Working invariants), `CONTRIBUTING.md`, `GOVERNANCE.md`,
`doc/POLICIES.md`, `doc/adr/0003-zero-unsafe-policy.md`,
`.github/workflows/ci.yml`, `RELEASE-NOTES-v0.0.*.md`. If this skill and
those files disagree, the files win — re-verify with the commands in
"Provenance and maintenance" at the bottom.

Jargon (ADR, MSRV, release branch, non-negotiable, satellite crate) is
defined once in `reference.md` §R1 and used verbatim below.

---

## 1. Classify the change first

Every change belongs to exactly one row. Pick the row before you write
code — the row tells you which gates to satisfy and whether an ADR is
required. Compact summary here; the exhaustive 9-row table (all classes,
triggers, branch prefixes, ADR triggers, extra gates) lives in
`reference.md` §R2.

| Class | Branch prefix | ADR? | Signature gate beyond default |
|---|---|---|---|
| **Bug fix** | `fix/` | No | Regression test in same commit. |
| **Feature** | `feat/` | **Yes** | Design issue first; changelog entry; example if new public entry point. |
| **Security / DoS fix** | `fix/` (private per `SECURITY.md`) | Yes if it changes parser accept set or adds a limit knob | Guard-firing regression test; changelog "Security" note; outranks every deadline (§3 law e). |

Six other classes (Restructure, Release, CI/build, Docs-only, Dep bump,
Performance) with their triggers, branch prefixes, ADR conditions, and
extra-gate detail: `reference.md` §R2.

> **When in doubt on ADR:** CONTRIBUTING.md litmus test — *"would I
> want a future contributor to read this before proposing the
> opposite?"* If yes, ADR. If no, commit message suffices.

---

## 2. Written non-negotiables

Every one of these is verified against source below. Row order is
enforcement severity.

### 2.1 Zero `unsafe` — forbidden, not merely denied

- Rule: `#![forbid(unsafe_code)]` at every crate root, **workspace-wide**.
- Verify: `grep -n unsafe_code crates/noyalib/Cargo.toml` — expect
  `unsafe_code = "forbid"` in the `[lints.rust]` table (currently
  `crates/noyalib/Cargo.toml:649`).
- Rationale: `forbid` (not `deny`) cannot be locally bypassed with
  `#[allow(unsafe_code)]`. ADR-0003 §*Alternatives considered* records
  the deliberate choice — mechanical enforcement a reviewer trusts
  without reading every diff.
- **Escape hatch: none.** Full exemption list + "you need memchr /
  smallvec instead" guidance in `reference.md` §R5.

### 2.2 CI must always be green — no bypasses, ever

- Rule: every push waits for CI. Any red job is fixed in the same
  session before declaring done. **Never** use `--no-verify`,
  `[skip ci]`, `if: false`, or hook-skipping flags.
- Verify: `head -33 PLAN.md` — *Working invariants* names each
  forbidden bypass.
- Rationale: CI integrity is a security control (§3 law e). The
  v0.0.9 → v0.0.11 cache-poisoning incident (§4 / `reference.md` §R4)
  showed "passing" CI can lie if scoped wrong — you cannot recover by
  lowering the bar.

### 2.3 Signed Conventional Commits with `Assisted-by:` trailer

- Rule: `git commit -S` on every commit; Conventional Commits format
  (`type(scope): summary`); `Assisted-by:` trailer added by the local
  `commit-msg` hook when an AI assistant contributed.
- Verify: `head -33 PLAN.md`; `sed -n '59,88p' CONTRIBUTING.md`.
- Rationale: unsigned commits are unmergeable (branch protection);
  `Assisted-by:` follows the Linux-kernel coding-assistants standard so
  AI provenance is auditable — `doc/POLICIES.md` §11.

### 2.4 One logical change per PR

- Rule: mechanical refactors and behaviour changes get separate PRs
  for blame hygiene. Feature + regression test ship in the **same**
  commit — never as follow-up (CONTRIBUTING.md § *Making changes* pt 3).
- Rationale: reviewer diff-reading budget is finite; a bisect landing
  on a mixed commit costs hours.

### 2.5 ADR required for load-bearing changes

Per `CONTRIBUTING.md` § *Architectural decisions*, an ADR is
mandatory when the change touches:

1. **Parse-output shape** — event stream, `Value` variants, CST node
   kinds.
2. **Public API surface** — new/removed items, changed signatures.
3. **Dependency floor (MSRV)** — a bump is a breaking event under
   §2.6.
4. **Core invariants** — the unsafe policy, panic policy, or a
   feature-flag semantic.

Skip the ADR at your peril — a PR that reviewers can't reconcile
against ADR precedent gets bounced.

### 2.6 MSRV bump = breaking event

- Rule: `noyalib` core MSRV bump is a **minor-version event**
  (breaking) — never a patch. Satellite MSRVs (`noya-cli` /
  `noyalib-lsp` / `noyalib-wasm` at 1.85.0) may bump on patch — they
  ship as application-style binaries.
- Current MSRV: **1.85.0** per `crates/noyalib/Cargo.toml`
  (`rust-version` is authoritative; `doc/POLICIES.md` §1 and
  `CONTRIBUTING.md` still cite 1.75.0 — stale drift, not a policy
  split). Arrived with `edition = "2024"`.
- Verify: `grep -n rust-version crates/noyalib/Cargo.toml`.
- Rationale + stale-drift diagnosis + enterprise-adoption backstory:
  `reference.md` §R6.

### 2.7 Panic policy — no panics on well-formed input

- Rule: library API does not panic on well-formed input. Permitted
  panic sites enumerated in `doc/POLICIES.md` §8 (tests / examples,
  internal `invariant_violated` sentinel, allocator OOM). Any new
  `unwrap()` / `expect()` / `panic!()` in a user-facing path fails
  review.
- Rationale: `panic = "abort"` in release means panics terminate the
  process — callers cannot recover.

### 2.8 No fabrication of API / flag / path / version references

- Rule: API names, flag names, file paths, version numbers, and CI
  matrix entries are checked against the source **before** the commit
  is written. Includes docstring examples, `README.md` snippets, and
  release-note code blocks.
- Verify: `head -37 PLAN.md`.
- Rationale: a fabricated symbol in the README is a broken doctest
  waiting to fire on `readme-examples` CI — historically the biggest
  source of red PRs.

---

## 3. Unwritten project laws (verified with maintainer 2026-07-08)

Not in the markdown files, but they gate merges and releases every bit
as hard as the written rules. Rule statements here; rationale +
worked-example prose for each law lives in `reference.md` §R7.

**(a) Same-session green.** Verify CI green after every push; any red
job is fixed in the same working session, never deferred.

**(b) Version-refs audit before "release PR is mergeable".** Before
declaring a release PR ready, sweep every surface for stale version
strings: `README.md`, rustdoc `//! # Examples`, `crates/*/examples/`,
`crates/*/benches/`, `CHANGELOG.md`, `RELEASE-NOTES-v0.0.<n>.md`, every
workspace `Cargo.toml`, and package manifests under `pkg/`.

**(c) `main` is protected — every change lands via PR + squash-merge.**
Direct pushes rejected. Even CI-config fixes go through a PR and merge
with `gh pr merge --squash --admin`.

**(d) No pre-emptive phasing of a maintainer-declared cut.** If the
maintainer frames a release as *complete* or *category-defining*, fix
everything inside that release — do not spin fixes into "next one".

**(e) Security > velocity, always.** A security, resilience, or CI-
integrity fix outranks any feature, deadline, or scheduled release.
Holding a release to land a security fix is the correct call every
time.

**(f) Community-PR takeover protocol.** External PRs (e.g. `zoosky`
#118 / #147–152, `canardleteer` #117) get **taken over**, rebased with
authorship preserved via `git am --3way`, credited in release notes,
and merged. Never left to rot; never merged unreviewed.

**(g) No perf claim ships without a Criterion run in the same PR.**
README, release-note, and rustdoc perf numbers cite a Criterion run
against a documented corpus, landed in the PR that introduced the
claim.

**(h) Hand-run commands ship as executable scripts, not snippets.**
When the maintainer must run something the tool cannot (signed-commit
flows, interactive prompts, destructive ops), write `./.git/<name>.sh`,
`chmod +x` it, and tell the maintainer to invoke it by path.

---

## 4. The historical incident behind the biggest CI rule

**Three-line summary.** For two full releases (v0.0.9 shipped, v0.0.10
shipped), the `no_std (alloc-only) build` CI job reported green in
~1.89s while a clean-target-dir build actually failed with 8 errors —
`Swatinem/rust-cache` was serving a matching-fingerprint hit from
`--all-features` jobs without exercising the no_std code path. The rule
that came out: every specialised CI job **MUST** set its own
`CARGO_TARGET_DIR` and a scoped `rust-cache` namespace, so "CI green"
means "green from a clean fingerprint," not "green from a cache hit."

Full narrative — what happened, why CI missed it, the PR #124 fix
trail, live `ci.yml` examples, and what "CI green" now means — lives in
`reference.md` §R4. Cross-reference sibling skill
`noyalib-failure-archaeology` for adjacent failure modes.

Quick verify the discipline is still in place:

```sh
grep -n CARGO_TARGET_DIR .github/workflows/ci.yml
git log --all --oneline --grep='cache-poisoning' -i
```

---

## 5. Review flow

Sequence for landing any change:

1. **Branch.** From `feat/v0.0.14` (current release branch — verify
   with `git branch --show-current` on a fresh clone), prefix per
   `CONTRIBUTING.md` § *Branch naming*.
2. **Local checks.** Minimum: `make` (check + clippy + test), plus
   `make fmt`, plus `make deny`. If your change touches a satellite
   crate you also run its per-crate MSRV.
3. **ADR if required** (see §2.5). ADR PRs can land in the same PR
   as the code they justify or in a preceding docs-only PR — the
   maintainer's call, but *before* the code merges.
4. **Signed Conventional Commit** with an `Assisted-by:` trailer.
   Regression test + code change in the **same** commit. New deps
   carry their one-line rationale in the commit body.
5. **Open the PR against the current release branch.** Title mirrors
   the commit format. Body has *What changed* (1–3 bullets), *Why*
   in plain English, and a *Test plan* the reviewer can green-check.
6. **CI runs the gate set.** Every job in `.github/workflows/ci.yml`
   `jobs:` must pass. The full current gate inventory (all 19 job
   names, with what each one checks) lives in `reference.md` §R3.
   Re-derive from `ci.yml` if the pipeline has moved on:

   ```sh
   grep -nE '^\s{2}[a-z][a-z0-9-]*:$' .github/workflows/ci.yml
   ```

   If any gate is red, apply unwritten law (a): fix in this session.

7. **One approval.** Maintainer approval per `CONTRIBUTING.md`
   § *Pull requests*.
8. **Squash-merge.** `gh pr merge --squash --admin` — no direct
   `main` push, no rebase-merge, no merge commit. Unwritten law (c).
9. **Verify CI green on `main` post-merge.** Same-session — law (a).

---

## 6. When NOT to use this skill

- Local gate runs, red-CI debug, release-tag cut → `noyalib-ci-and-release`.
- Evidence a change needs (tests, benches, doctests, corpus) →
  `noyalib-validation-and-qa`.
- Long-form failure archaeology / how prior incidents shaped policy →
  `noyalib-failure-archaeology` (companion to §4 / `reference.md` §R4).
- Parser internals → `doc/design/`, `doc/ARCHITECTURE.md`, ADRs.

This skill answers *"can I?"* / *"what does the project require of
me?"*. Not *"how do I?"*.

---

## Provenance and maintenance

Covers **both** `SKILL.md` and `reference.md` in this directory.
Volatile facts date-stamped **2026-07-08**, release branch
**`feat/v0.0.14`**. Re-verify with these one-liners; if a fact drifts,
edit *both* files in the same PR that changes the source:

```sh
git branch --show-current                                  # release branch
grep -Rn 'unsafe_code = "forbid"' crates/*/Cargo.toml      # zero-unsafe
sed -n '19,42p' PLAN.md                                    # working invariants
sed -n '110,135p' CONTRIBUTING.md                          # ADR triggers, MSRV
sed -n '34,58p' doc/POLICIES.md                            # (stale-drift point)
grep -Rn 'cache-poisoning\|CARGO_TARGET_DIR' .github/workflows/ci.yml
git log --all --oneline --grep='cache-poisoning' -i
grep -nE '^\s{2}[a-z][a-z0-9-]*:$' .github/workflows/ci.yml  # gates → §R3
grep -n '^rust-version' crates/noyalib/Cargo.toml          # MSRV floor
```

If any diverges from what this skill claims, edit the skill in the same
PR that changes the source — do not let these files lag the repo.
