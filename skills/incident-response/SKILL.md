---
name: incident-response
description: "Restore service first, find the cause afterwards. Load when something is broken in production right now: an outage, a bad deploy, data at risk, alerts firing, users affected. Prioritises mitigation over diagnosis, keeps a running timeline, and defers the root cause to a blameless follow-up. Not for unhurried debugging of a reproducible defect."
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Write Edit Bash"
metadata:
  agtmls-version: "0.0.4"
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-risk-level: "low"
  agtmls-network-access: "none"
  agtmls-writes-files: "true"
  agtmls-executes-commands: "true"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Incident response

**Trigger.** Something is broken **now** and someone is affected: an outage,
errors spiking after a deploy, data being written wrongly, a security alert, a
pager. The distinguishing feature is not difficulty — it is that time is
costing something.

> **Reference material** (severity rubric, mitigation menu, comms templates,
> and running the blameless postmortem): see `reference.md` in this directory.

## The rule

> **Stop the bleeding before you understand the wound.**

This inverts normal engineering discipline, and deliberately. `systematic-debugging`
says *no edit before an explanation* — correct when the only cost is your
time. In an incident the cost is accruing per minute, and a mitigation you do
not fully understand is usually better than a correct fix you do not have yet.

The trap is the opposite instinct: an engineer who finds the cause
interesting will investigate while users stay broken. Resist it.

## The order

### 1. Assess — one minute

- **What is the user-visible impact?** Not "the queue is backed up" but "no
  one can check out".
- **How many, and how badly?** All users or one region? Degraded or dead?
- **Is data at risk?** Corruption or loss changes everything: it can outlive
  the outage and may be unrecoverable. Prioritise stopping the writes.
- **Is it getting worse?**

### 2. Communicate — immediately, then on a clock

Say something within minutes, even with nothing to report:

> Investigating elevated 500s on checkout since 14:02. Impact: roughly 30% of
> checkout attempts failing. No cause yet. Next update 14:30.

Then keep the interval, whether or not there is news. Silence is read as
either "nothing is happening" or "it is worse than they are saying", and both
cost you more than an unglamorous update.

**Nominate one coordinator** if more than two people are involved. Their job
is deciding and communicating, not typing commands.

### 3. Mitigate

Reach for the fastest safe lever, in roughly this order:

| Lever | When |
| --- | --- |
| **Roll back** | Correlates with a deploy. Almost always first. |
| **Feature flag off** | The path is flagged |
| **Scale up / restart** | Resource exhaustion or a wedged process |
| **Shed load / rate-limit** | Overload, cascading failure |
| **Fail over** | One region, node, or dependency is bad |
| **Block the write path** | Data is being corrupted — stop it even at the cost of availability |
| **Forward fix** | Only when rollback is impossible and the change is small and understood |

**Rollback is not defeat.** "Deployed at 13:58, errors at 14:02" is enough
correlation to act on. You do not need to know *why* to roll back, and
rolling back a good deploy costs far less than debugging a bad one live.

### 4. Verify the mitigation

Confirm with the same signal that showed the problem — the error rate, the
dashboard, a real request. "It should be fixed now" is how an incident gets
declared over twice. See `verification-before-completion`.

### 5. Stand down, then diagnose

Once impact has stopped, **the incident is over and the investigation
begins** — and it begins under `systematic-debugging`, not here. Do not keep
the incident open for the root cause, and do not skip the investigation
because the symptom is gone.

## Keep a timeline as you go

Write it *during*, not after. Memory reorders under stress and the timeline
is what makes the follow-up honest.

```
14:02  alerts: checkout 500s at 30%
14:04  posted first update
14:07  noticed deploy #4821 at 13:58 — correlated
14:09  rolled back #4821
14:13  error rate back to baseline; confirmed with a real checkout
14:20  stood down; investigation moved to #incident-4821
```

Timestamps, actions, observations. Not analysis — that comes later.

## Anti-patterns

- **Debugging while the site is down.** The most common and most expensive.
- **Multiple people changing production at once.** One pair of hands, or you
  will not know which action did what.
- **Silent heroics.** Fixing without telling anyone means duplicate effort and
  no timeline.
- **Skipping the write-up** because it turned out to be simple. Simple causes
  recur.
- **Blame.** It ends the flow of information, which is the only thing keeping
  the next incident short.

## When not to use

- The defect is reproducible and nothing is on fire: `systematic-debugging`.
- A failing test or a red CI run with no user impact.
- Planned degradation you already knew about.
