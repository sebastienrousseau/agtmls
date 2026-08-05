<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Incident response — reference

Depth for `SKILL.md`. Load when you need to size an incident, choose between
mitigations, write the comms, or run the follow-up.

## Severity

Size by **impact**, not by how interesting the cause is.

| Sev | Shape | Response |
| --- | --- | --- |
| **1** | Core function unusable for most users; data loss or corruption; security breach | Wake people. Coordinator + comms. Mitigate at any cost short of making it worse. |
| **2** | Major degradation, or one segment fully broken | Work it now, business hours or not. Regular updates. |
| **3** | Minor or cosmetic; a workaround exists | Ticket it. No pager. |

Two calibration notes:

- **Data at risk is always at least Sev 1**, even if availability looks fine.
  An outage ends; corruption propagates into backups and downstream systems.
- **When unsure, size up.** Downgrading a Sev 1 costs an apology.
  Under-calling a Sev 2 costs the outage.

## The mitigation menu

### Roll back

The default. Fast, well-understood, and reversible.

Rolling back is wrong only when: the deploy included an irreversible
migration; rolling back loses data written under the new schema; or the
problem predates the deploy and the correlation is coincidence.

Know in advance whether your migrations are backward-compatible — that
question decides whether rollback is available, and answering it mid-incident
is expensive.

### Feature flag

Faster than a rollback when available, and narrower. Requires that the path is
already flagged; you cannot add one during an incident.

### Restart / scale

Effective for resource exhaustion — memory leaks, connection-pool starvation,
a wedged thread. Buys time rather than fixing anything, and the incident is
not over just because the restart worked. Note *what* was exhausted; that is
the diagnosis lead.

### Shed load

When the system is overloaded, serving 70% of traffic beats collapsing under
100%. Rate-limit, disable the expensive endpoint, queue and drain, or return a
cached or degraded response. Choose deliberately who gets shed.

### Stop the writes

When data is being corrupted, availability is the *cheaper* thing to lose.
Take the write path down, then work out the blast radius: how many records,
since when, recoverable from where.

### Forward fix

Last resort. Only when rollback is unavailable **and** the change is small and
fully understood. Under time pressure the odds of a second incident from a
rushed fix are high. If you must, have someone else read the diff.

## Communication templates

**First contact — within minutes, before you know anything:**

> Investigating elevated errors on <surface> since <time>. Impact: <what
> users experience>. Cause not yet known. Next update at <time>.

**Update — on the clock, even without news:**

> Update <time>. Still investigating. We have ruled out <X>. Impact unchanged
> at <scope>. Next update <time>.

**Mitigated — separate this clearly from "fixed":**

> <time>: mitigated by rolling back <deploy>. Error rate back to baseline,
> confirmed by <signal>. Root cause not yet known; investigation continues in
> <channel>. No further impact expected.

**Resolved:**

> Resolved. <Duration> of <impact> affecting <scope>. Cause: <one line>.
> Follow-up: <link>.

Two rules: never say "fixed" when you mean "mitigated", and never give an ETA
you are not confident in. A missed ETA costs more trust than no ETA.

## The follow-up

Within a few days, while memory is fresh. **Blameless**: the question is what
about the *system* let this happen, not who typed the command. The moment
people expect blame, they stop volunteering the details that make the analysis
useful.

Cover:

- **Impact** — duration, scope, what users experienced.
- **Timeline** — the one you kept during, not a reconstruction.
- **Root cause** — from `systematic-debugging`, not from the mitigation.
  "Rolled back the deploy" is what you did, not why it broke.
- **Detection** — how long until you knew? If a user told you before the
  alerts did, that is a finding in itself.
- **What went well** — genuinely. It identifies what to keep.
- **Actions** — each with an owner and a date, and each *specific*. "Be more
  careful" is not an action; "add a schema-compatibility check to the deploy
  pipeline" is.

The highest-value output is usually not the fix for this cause. It is the
detection or mitigation improvement that shortens the *next* incident,
whatever causes it.

## Interaction with other skills

- `systematic-debugging` owns the root cause, **after** stand-down. Feed it the
  timeline; the mitigation that worked is strong evidence about the cause.
- `verification-before-completion` is what stops a premature all-clear.
- `handoff` matters for a long incident spanning shifts: tree state, what has
  been tried, what has been ruled out.
- `receiving-code-review` applies to the forward fix — get a second reader
  even under pressure, especially under pressure.
