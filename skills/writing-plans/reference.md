<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Writing plans — reference

Depth for `SKILL.md`. Load when you need the plan template, a worked example
of a weak plan rewritten, sizing heuristics for unfamiliar work, or the rules
for revising a plan mid-flight.

## Template

```markdown
## Goal
<One sentence, stated as an observable outcome.>

## Baseline
<What works today. The command you ran and what it reported.>

## Assumptions
- <Decision made without asking, and why it is the reasonable reading.>

## Not in scope
- <Explicitly excluded work.>

## Steps
1. **<Action>**
   - Done when: <observable condition>
   - Verify: `<command>`
2. ...

## Open questions
- <Anything that must be answered by someone else, and by when.>
```

The `Baseline` section is the one most often skipped and the most valuable in
retrospect: without it, a failure three steps in cannot be attributed to your
change rather than to a tree that was already broken.

## A weak plan, rewritten

**Weak:**

> 1. Look at the auth code
> 2. Refactor it to support OAuth
> 3. Add tests
> 4. Update docs

Four problems. Step 1 is not a change. Step 2 is unbounded and unverifiable.
Step 3 defers the tests to the end, so nothing is checkable until then. No
baseline, no scope boundary, no ordering rationale.

**Rewritten:**

> **Goal:** users can authenticate with Google OAuth in addition to the
> existing password flow.
>
> **Baseline:** `pytest tests/auth/` — 31 passed. Password login works
> against the dev server.
>
> **Assumptions:** we use the existing `authlib` dependency rather than
> adding a new one; token storage reuses the current session table.
>
> **Not in scope:** SAML, account linking for existing users, admin UI.
>
> 1. **Extract `AuthProvider` protocol from `PasswordAuth`.**
>    Done when: `PasswordAuth` implements it and nothing else changed.
>    Verify: `pytest tests/auth/` still 31 passed.
> 2. **Add `GoogleAuth` implementing the protocol, token exchange only.**
>    Done when: `test_google_exchanges_code_for_token` goes red→green
>    against a recorded response.
>    Verify: `pytest tests/auth/test_google.py`.
> 3. **Wire the provider into the login route behind `AUTH_GOOGLE=1`.**
>    Done when: flag off = current behaviour; flag on = redirect issued.
>    Verify: `pytest tests/auth/` (both flag states), 33 passed.
> 4. **Document the two env vars in README + `.env.example`.**
>    Done when: a fresh clone following the README completes a Google login.
>    Verify: run the documented steps in a clean checkout.
>
> **Open questions:** which Google project owns the client ID in production?
> Needed before step 3 ships, not before it is written.

Each step is revertible, verifiable, and leaves the suite green. The risky
unknown (token exchange) is step 2, not step 4.

## Sizing heuristics

- **The revert test.** If the step were rejected in review, could you drop it
  without unpicking later steps? If not, split it.
- **The sitting test.** A step you cannot finish in one focused sitting will
  be interrupted mid-way, leaving the tree in a state nobody can check.
- **The one-check test.** If a step needs three unrelated verifications, it
  is three steps.
- **The diff-kind test.** Mechanical (rename, move, format) and semantic
  (behaviour) changes belong in different steps, always. Mixing them makes
  the semantic change unreviewable inside the noise.

For unfamiliar territory, add an explicit **spike** step with a time or scope
box and a decision as its done-condition:

> 0. **Spike: can `authlib` do PKCE without a custom client?**
>    Done when: a throwaway script completes a PKCE exchange, or we conclude
>    it cannot and record why.
>    Verify: the script runs, or the note is written. Code is discarded
>    either way.

## Revising mid-execution

Plans are expected to be wrong somewhere. What matters is that the revision
is visible.

**Revise when:** a step reveals the approach cannot work; a done-condition
turns out to be unobservable; new required work appears; or an assumption is
falsified.

**How:**

1. Stop at the current step boundary — not mid-step.
2. State what you learned and which step it invalidates.
3. Rewrite the affected steps, keeping completed ones as history.
4. If the *goal* changed rather than the route, that is a scope change: say
   so and get confirmation before continuing.

**Do not** quietly work around a broken plan. The reader is tracking your
stated steps; divergence without notice means their model of the work is
wrong, which is worse than having no plan at all.

## Handing a plan over

A plan that survives a session boundary becomes a handoff: the step list plus
current state, tree state, the next concrete action, and the traps you hit.
Load `handoff` for the template and the failure modes — a plan alone leaves
out exactly the parts a successor cannot reconstruct from the code.

## Interaction with other skills

- `verification-before-completion` supplies the standard each
  done-condition must meet — an observation, not an impression.
- `test-driven-development` often *is* the step body: "red test, then code"
  is a natural done-condition pair.
- `systematic-debugging` precedes planning for defect work; you cannot plan
  a fix you cannot explain.
- A project's own change-control or ADR process takes precedence on what
  needs approval and when.
