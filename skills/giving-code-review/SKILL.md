---
name: giving-code-review
description: "Review someone else's change so the feedback is actionable and proportionate. Load when reading a pull request, diff, or patch you did not write, and when deciding whether a concern is blocking or merely a preference. Prioritises correctness over style, labels every comment with its severity, and separates what must change from what you would have done differently."
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Write Edit"
metadata:
  agtmls-version: "0.0.5"
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-risk-level: "low"
  agtmls-network-access: "none"
  agtmls-writes-files: "true"
  agtmls-executes-commands: "false"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Giving code review

**Trigger.** You are reading a change you did not write and are expected to
respond: a pull request, a patch, a diff, a colleague asking "does this look
right?".

> **Reference material** (the correctness pass in detail, severity calibration,
> worked comment rewrites, and reviewing agent-authored changes): see
> `reference.md` in this directory.

## The rule

> **Every comment states its severity. A reviewer who does not distinguish
> "this is broken" from "I'd have named it differently" makes both easy to
> ignore.**

Unlabelled feedback forces the author to guess what blocks the merge, and
they guess wrong in both directions — polishing nits while shipping the bug,
or dismissing a real defect as taste.

## Read in this order

Reading a diff top-to-bottom is how correctness bugs get missed while
indentation collects three comments. Work outward instead:

1. **Does it do the right thing?** Read the description and the tests before
   the implementation. If you cannot tell what the change is *for*, that is
   your first comment.
2. **Is it correct?** Trace the logic — boundaries, error paths, concurrency,
   the empty case and the enormous one.
3. **Will it hold up?** Security, performance at real scale, failure modes,
   backward compatibility.
4. **Is it maintainable?** Naming, structure, duplication, comments that will
   go stale.
5. **Is it consistent?** House style and formatting. Last, and usually a
   linter's job rather than a human's.

Run out of time and you have still covered the levels that matter.

## Label every comment

| Label | Meaning | Author must |
| --- | --- | --- |
| **blocking** | Wrong, unsafe, or breaks something | Fix before merge |
| **should** | A real problem, not merge-blocking | Fix or justify |
| **consider** | A genuine option with trade-offs | Decide either way |
| **nit** | Preference, no correctness content | Free to ignore |
| **praise** | Good, and worth keeping | Nothing |
| **question** | You genuinely do not know | Answer |

Two rules follow:

- **Be honest about the ratio.** If everything is blocking, nothing is. Most
  comments on a competent change are `nit` or `consider`.
- **`question` must be a real question.** "Why would you do it this way?" is
  criticism in costume — say the criticism instead.

## Make comments actionable

A comment the author cannot act on is noise. Three parts: **what**, **why**,
**what instead**.

| Weak | Strong |
| --- | --- |
| "This is wrong." | "**blocking**: `rows[0]` raises on empty input — `load('')` reaches it. Guard, or return `None`." |
| "Use a map here." | "**consider**: O(n²) over `users`; a dict keyed by id makes it O(n). Matters above a few hundred." |
| "Bad naming." | "**nit**: `d` → `deadline`; the type isn't obvious at the call site." |
| "Needs tests." | "**should**: nothing covers the retry path. `test_retries_on_timeout` with a mock clock would pin it." |

Point at the line, say what breaks, offer a direction. You do not owe a full
solution, but "this is wrong, figure it out" is not review.

## Proportion

Match depth to stakes. A config tweak and a new auth path do not deserve the
same scrutiny, and treating them alike trains people to ignore you.

- **Do not redesign in review.** If the approach is wrong, say so once, early,
  at the top level — not through twenty inline comments implementing your
  version.
- **Do not block on preference.** Correct, tested, and readable means your
  taste is not a merge condition.
- **Do not review the author.** Comment on the code.
- **Approve when it is good enough**, not when it is what you would have
  written. Perfect is a way of never shipping.

## When not to use

- You wrote the change — that is `receiving-code-review`.
- The project defines its own review protocol or approval rules; follow it.
- You are auditing for a specific risk class rather than reviewing a change.
