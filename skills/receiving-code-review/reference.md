<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Receiving code review — reference

Depth for `SKILL.md`. Load when a thread is going badly, when you believe the
reviewer is wrong and need to establish that responsibly, or when the change
under review was written by an agent.

## Worked replies by category

### Defect

> **Reviewer:** This will throw if `rows` is empty — `rows[0]` on line 44.

Fix, verify, and reply with the evidence. Do not just say "good catch, fixed".

> Fixed. Added the empty guard at `loader.py:44` and
> `test_load_empty_returns_none`, which raises `IndexError` on the previous
> commit and passes now.

### Risk

> **Reviewer:** This works but it assumes the callback never re-enters.

Either address it or record the acceptance — an unanswered risk comment
becomes an incident report later.

> Accepted rather than fixed: `_flush` is only reachable from the single
> writer task, and re-entry would need a second one. I've asserted that
> invariant at the top of the function so it fails loudly if that changes.

### Design

The one worth spending time on. State the trade-off in terms both of you can
check, and name what would change your mind.

> **Reviewer:** Why a state machine? A couple of booleans would do.

> Two booleans give four states and only three are legal — the
> `draining && !started` combination is the bug we hit in #388. The machine
> makes that unrepresentable. It costs ~20 lines. If you'd rather have the
> booleans plus an assertion, I'll take that; I mainly want the illegal state
> to be impossible or loud.

### Preference

> **Reviewer:** We usually name these `*_handler`.

Accept and move on. There is no version of this worth a thread.

### Question

> **Reviewer:** What does `mode=2` mean here?

Answer, then fix the cause.

> It's "append without truncate". You're right that it's opaque — replaced
> the literal with `FileMode.APPEND` so the next reader doesn't have to ask.

### Misunderstanding

Clarify without scoring a point, then ask what misled them.

> The retry only wraps the network call — the DB write on line 60 is outside
> the block. That said, the nesting makes it easy to misread; I've pulled the
> retried section into `_fetch_with_retry` so the boundary is explicit.

## When you believe the reviewer is wrong

They are sometimes wrong. The burden is on you, and it is discharged with
evidence, not confidence.

1. **Re-read the comment assuming they are right.** A large share of "the
   reviewer is wrong" resolves here — they saw something you did not.
2. **Reproduce their claim.** If they say it breaks on empty input, run it on
   empty input. If it does not break, you now have a fact rather than an
   opinion.
3. **Reply with the observation**, not the assertion:
   - Weak: "That's not how it works."
   - Strong: "I tried it — `parse('')` returns `[]` rather than raising; test
     at `tests/test_parse.py:31`. Am I missing a path where it does throw?"
4. **Leave the door open.** The trailing question is not politeness; it is
   how you find out you are the one who is wrong.
5. **Escalate on the third exchange, not the sixth.** If two rounds have not
   converged, the thread is the wrong medium. Get a synchronous decision or a
   third opinion.

**Never** silently ignore a comment you disagree with. A reviewer who finds
their concern unaddressed and unmentioned stops trusting the whole review.

## The "make the change, then argue" ordering

When a requested change is cheap and reversible, and the disagreement is
mild, doing it first and discussing after is often the fastest correct path —
you unblock the merge and keep the argument alive at low cost.

Do **not** do this when the change is a defect in your view. Making a change
you believe is wrong, to close a thread, is how known bugs ship with two
people's approval.

## Reviewing agent-authored changes

If the change under review was produced by an agent (including you), two
extra checks apply, because the usual signals are absent:

- **Confidence is not evidence.** Agent-authored code arrives with fluent
  justification regardless of whether it was verified. A comment asking "did
  you run this?" deserves a literal answer, not a restatement of intent.
- **Plausible-but-unused code.** Agents produce helpers that look right and
  are never called, error branches that cannot trigger, and tests that assert
  tautologies. Reviewers rightly flag these; the correct response is deletion,
  not justification.

When you are the agent, the honest reply to "did you test this?" is sometimes
"no" — say it. See `verification-before-completion`.

## Interaction with other skills

- `verification-before-completion` applies to every review fix: a fix
  reported as done without observation is the same defect as any other.
- `test-driven-development` supplies the shape of a defect fix — red test
  from the reviewer's described input, then the change.
- `handoff` matters when a review spans sessions: the open threads and their
  decisions are exactly the state a successor needs.
- The project's own PR workflow governs approvals, required reviewers, and
  merge mechanics.
