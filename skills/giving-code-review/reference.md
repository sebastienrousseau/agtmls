<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Giving code review — reference

Depth for `SKILL.md`. Load when you need the correctness checklist, severity
anchors, worked comment rewrites, or the extra checks for agent-authored code.

## The correctness pass, in detail

Correctness is where review earns its cost. What to actually look for:

**Boundaries.** Empty, one, many, maximum. Off-by-one in slices and ranges.
The first and last iteration of every loop.

**Error paths.** Every `try`/`catch`/`Result`: handled or swallowed? Does a
partial failure leave consistent state? Is the message useful at 3am?

**Nullability.** Every value that can be absent. Does the code assume
presence anywhere it is not guaranteed?

**Concurrency.** Shared mutable state. Is the lock held across the whole
invariant or only part of it? Can two calls interleave destructively? Is
anything assumed atomic that is not?

**Resource lifetime.** Files, sockets, connections, locks — closed on every
path, including the error one?

**Idempotence.** If this runs twice — retry, redelivery, double-click — is
the result the same?

**Trust boundaries.** Input from outside: validated? Interpolated into SQL, a
shell command, HTML, or a filesystem path?

## Severity, calibrated

Miscalibration is the most common reviewer failure. Anchors:

**blocking** — data loss or corruption; a security hole; a crash on a
reachable path; a breaking change to a published contract; a test that
asserts nothing; a secret in the diff.

**should** — missing test for new behaviour; an error swallowed silently; a
performance cliff at plausible scale; a leaked resource on the error path;
duplication that will certainly diverge.

**consider** — a simpler structure exists; a stdlib function replaces this;
an abstraction is premature; a name is misleading but not wrong.

**nit** — formatting a linter should own; word choice in a comment; import
order.

Writing `blocking` more than a couple of times on a routine change means
either the change needs a conversation rather than comments, or you are
inflating.

## Comment rewrites

**Vague to specific**

> ~~"I don't think this handles errors properly."~~
> **should**: if `fetch()` raises, `conn` at line 40 is never closed. Use
> `with`, or close in a `finally`.

**Prescriptive to reasoned**

> ~~"Use a dataclass."~~
> **consider**: this dict is built in three places with the same five keys — a
> dataclass makes a missing key a type error instead of a runtime `KeyError`.
> Your call; a dict is fine while it stays local.

**Rhetorical to direct**

> ~~"Is there a reason you're not using the existing helper?"~~
> **should**: `utils.parse_duration` already does this and handles the `ms`
> suffix, which this version drops. Was reimplementing deliberate?

**Pile-on to single top-level**

Twenty inline comments all saying "this should be a state machine" is one
comment. Put it at the top level, once, with the reasoning, and let the author
decide before reworking twenty lines.

## When you cannot fully evaluate it

Say so. A review implying more scrutiny than it received is worse than a short
one.

> I reviewed the API surface and error handling; both look right. I have not
> evaluated the CRDT merge logic — I do not know this algorithm well enough to
> call it correct. Someone who does should read `merge.py:60-140` first.

That is a useful review. "LGTM" on code you did not understand is not.

## Reviewing agent-authored changes

The usual signals are missing: there is no hesitation in the prose to read,
and the justification is fluent whether or not anything was verified. Three
checks that earn their place:

**Ask what was executed.** Not "does this work" but "what did you run, and
what did it print?" A confident description of behaviour is not an
observation. "I could not run it" is a fine answer and changes how you review.

**Look for plausible-but-dead code.** Helpers never called, error branches
that cannot trigger, config options nothing reads. These pattern-match to good
code and are pure maintenance cost. Delete rather than justify.

**Check the tests fail without the change.** Agent-authored tests are often
written after the code and pass on first run, which proves only that the
harness executes. Ask — or `git stash` the source change and run them.

## Interaction with other skills

- `receiving-code-review` is the other half; these labels are what make its
  triage table work.
- `verification-before-completion` sets the bar you hold the author to: a
  claim needs an observation.
- `test-driven-development` is what "did this test ever fail?" is checking.
- The project's own review protocol governs approvals and merge mechanics.
