<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Handoff — reference

Depth for `SKILL.md`. Load when you need the template, a worked comparison,
or the extra state that long-running and multi-agent work requires.

## Template

```markdown
## Goal
<Observable outcome. What "done" looks like.>

## Tree state
- Branch: <name>, based on <base>
- Uncommitted: <coherent | mid-edit | none> — <what>
- Stashed: <what, or none>
- Half-applied: <migrations, renames, upgrades — or none>
- Builds/tests currently: <green | red, and how>

## Done
- <Claim> — evidence: <command + what it reported>

## Next action
<The literal command or edit to start with.>

## Dead ends
- <What was tried, why it failed, how long it cost.>

## Open questions
- [BLOCKING] <question> — owner: <who>
- <non-blocking question>
```

`Tree state` first, `Next action` in the middle where it is impossible to
miss. If you write nothing else, write those two.

## A weak handoff, rewritten

**Weak:**

> I've been working on the OAuth integration. Got quite far with the token
> exchange — had some trouble with the redirect URI but I think it's mostly
> sorted now. Tests are mostly passing. Next step is to finish wiring it up
> and then it should be ready for review.

Nothing here is actionable. "Mostly sorted", "mostly passing", and "finish
wiring it up" each hide a question the reader must come back and ask. The
redirect-URI trouble — the one genuinely valuable detail — is mentioned
without content.

**Rewritten:**

> **Goal:** users can log in with Google; password login keeps working.
>
> **Tree state:** branch `feat/oauth` off `main@a3f81c2`. Uncommitted changes
> in `auth/google.py` are coherent (complete token exchange). Nothing
> stashed. `pytest tests/auth/` — 33 passed, 1 failed
> (`test_callback_redirect`, see below).
>
> **Done:**
> - `AuthProvider` protocol extracted; `PasswordAuth` implements it.
>   Evidence: `pytest tests/auth/` was 31 passed before and after.
> - Google token exchange works. Evidence:
>   `test_google_exchanges_code_for_token` red→green against a recorded
>   response.
>
> **Next action:** `pytest tests/auth/test_callback.py::test_callback_redirect`
> fails because the callback builds the redirect URI from `request.host`,
> which is `testserver` under the test client. Make it read
> `settings.PUBLIC_URL` instead — `auth/google.py:71`.
>
> **Dead ends:**
> - Registering `http://localhost:8000` in the Google console does not help;
>   the mismatch is our side, not theirs. ~40 minutes.
> - `authlib`'s `authorize_redirect` helper hardcodes `request.url_for`, so
>   we cannot use it here. Do not retry.
>
> **Open questions:**
> - [BLOCKING] which Google Cloud project owns the production client ID?
>   Owner: platform team. Blocks deploy, not further development.

Same work, same length. The difference is that the reader's first move is
unambiguous and they will not spend 40 minutes on the console again.

## Long-running work

When work spans many sessions, the handoff accumulates and needs pruning or
it becomes an unreadable log:

- **Keep the trap list; compress the done list.** Completed work is visible
  in the diff. Dead ends are not recorded anywhere else.
- **Collapse resolved questions** into a one-line decision with its reason —
  "decided: reuse the session table, avoids a migration" — and delete the
  discussion.
- **Re-verify before re-handing.** Evidence from three sessions ago is not
  evidence. Re-run and restate, or mark it as last observed on a given date.
- **Keep it in the repo**, not in a chat message, if the work will outlive
  the conversation. A file on the branch travels with the code.

## Multi-agent and cross-tool handoff

When the successor is a different agent, tool, or model, assume **none** of
your context survives — not the conversation, not the reasoning, not the
files you had open. Two additions:

- **Name the entry points explicitly.** Absolute or repo-relative paths with
  line numbers. "The handler" means nothing to a fresh reader.
- **State the constraints you were working under**, especially ones that are
  not visible in the code: an API you must not change, a dependency you were
  told not to add, a performance budget. A successor without these will
  cheerfully violate them.

If the successor is an agent that will act without a human reviewing each
step, mark anything destructive or outward-facing as requiring confirmation.

## What not to include

- Your reasoning process, except where it produced a trap.
- Restatements of what the code says. The reader can read the code; they
  cannot read your failed attempts.
- Praise, apology, or hedging about the state of the work. State it plainly.
- Speculation about difficulty. "This should be easy" is unfalsifiable and
  routinely wrong.

## Interaction with other skills

- `writing-plans` supplies the step list a handoff reports progress against;
  a plan plus a tree-state section is most of a handoff already.
- `verification-before-completion` sets the bar for the `Done` section —
  every claim carries the observation that justifies it.
- `receiving-code-review` produces state worth handing over: which threads
  are open, and what was decided on the closed ones.
- `systematic-debugging` produces the explanation and the dead ends; if you
  hand off mid-investigation, the Phase 2 boundary you established is the
  single most valuable thing to record.
