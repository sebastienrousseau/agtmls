<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Brainstorming — reference

Depth for `SKILL.md`. Load when you need a question bank for a specific
request shape, techniques for a requester who cannot articulate what they
want, or a worked vague-to-spec transcript.

## Question banks by request shape

Use these to *find* the blocking questions, not to ask them all.

### "Build me X"

- Who uses it, and what do they do today instead?
- What is the smallest version that would be worth having?
- What must it integrate with that already exists?
- What is explicitly out of scope for this round?
- What does failure look like — degraded, offline, or wrong?

### "Make it faster"

- Which operation, measured how, at which percentile?
- What is it now, and what would be good enough?
- Is the constraint latency, throughput, or cost?
- What may I trade — memory, staleness, accuracy, complexity?
- Is there a known hotspot, or is this a hunch?

### "Add auth" / any security-adjacent ask

- Authenticating whom, to what, against which store?
- Session model: token lifetime, refresh, revocation?
- What happens to existing users and existing sessions?
- Which compliance or audit requirements apply?
- Who decides the threat model, and has it been written down?

### "Clean this up" / "refactor X"

- What problem is the current shape causing? (If none, why now?)
- Is behaviour allowed to change at all?
- What is the test coverage on the affected code today?
- Is anything else being built on top of it right now?

### "Migrate to Y"

- What forced the move — support, cost, capability, or preference?
- Big-bang or incremental, and can both run at once?
- What is the rollback if it goes wrong mid-way?
- Who else depends on the current behaviour?

## When the requester cannot articulate it

Common and not their fault. Four techniques that beat asking harder:

**Show a strawman.** A concrete wrong proposal gets a better response than an
open question. People correct far more readily than they specify.

**Ask for an example.** "Walk me through one real case, start to finish."
Concrete beats abstract, and the walk-through exposes the steps they forgot
to mention.

**Ask what would make it a failure.** Inverting is often easier: people who
cannot define success can usually name what would make them unhappy.

**Ask what exists now.** The current workaround — the spreadsheet, the manual
step, the script somebody runs — is the real requirements document.

## Vague to spec, worked

**The ask:**

> Can you add caching to the API? It's slow.

**Weak response:** implement a cache. You have now guessed the layer, the
key, the TTL, the invalidation strategy, and whether staleness is acceptable
at all — five decisions, none of them yours.

**Strong response:**

> Before I add a cache — a few things that change the approach:
>
> 1. Which endpoint is slow, and how slow? If it is the `/search` p99 rather
>    than the mean, a cache may not be the fix.
> 2. Can responses be stale, and for how long? That decides whether this is a
>    cache or an index problem.
> 3. Is the data per-user or shared? Per-user caches at this traffic mostly
>    add memory pressure without hit rate.
>
> Assuming shared data and 60s staleness being acceptable, I would put a
> read-through cache in front of the query layer. Say if either assumption is
> wrong.

Three questions, each with a stated consequence, plus a default so the work
can start if they are busy. That last part matters: a question with no
fallback blocks; a question with a stated assumption does not.

## The spec artifact

Keep it to a paragraph or two. If it grows past a page, either the request is
genuinely large — in which case it wants `writing-plans` next — or you are
specifying things nobody asked about.

```markdown
**Goal:** <observable outcome>
**In scope:** <what will change>
**Not in scope:** <what deliberately will not>
**Assumed:** <decisions made without asking, and why they are reasonable>
**Open:** <what is still blocking, and who owns it>
**Done when:** <the check that settles it>
```

`Not in scope` and `Assumed` are the two lines people skip and the two that
prevent the most rework.

## Interaction with other skills

- `writing-plans` takes this output as input: you cannot decompose a goal you
  have not pinned down.
- `verification-before-completion` uses `Done when` as the completion bar.
- `receiving-code-review` is where an unstated assumption surfaces if you
  skipped this step — usually as "this isn't what I asked for".
