---
name: brainstorming
description: "Turn a vague request into a specification before any plan or code exists. Load when an ask is underspecified, when a feature request arrives with no acceptance criteria, or when you notice you are guessing at what someone wants. Surfaces the decisions, constraints, and deliberate non-goals by asking rather than assuming. Not for diagnosing a defect."
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

# Brainstorming

**Trigger.** The request is a direction, not a specification: *build me a
dashboard*, *make this faster*, *we need auth*, *clean this up*. Also load it
the moment you catch yourself inventing a requirement to fill a gap.

> **Reference material** (question banks by request type, elicitation
> techniques, and worked vague-to-spec transcripts): see `reference.md`.

## The rule

> **Ask about what changes the work. Assume the rest and say so.**

The failure is not asking too few questions — it is asking the *wrong* ones.
Twenty clarifications on a two-line fix is its own kind of unhelpful. The
test for every question: **would two plausible answers lead to materially
different work?** If not, pick the sensible default, write it down as an
assumption, and move on.

## The loop

### 1. Restate the goal as an outcome

Not the mechanism the requester happened to name. *"Make the API faster"* is
a mechanism; *"the search page responds in under 300ms at p95"* is an
outcome. If you cannot state an outcome, that is your first question.

Restating also catches the most expensive failure early: solving the wrong
problem competently. Say it back and let them correct you.

### 2. Find the decisions hiding in the ask

Read the request for **unbound variables** — places where you would have to
choose, and where a wrong choice is costly:

| Variable | Question it implies |
| --- | --- |
| Scope boundary | What is explicitly *not* included? |
| Users | Who uses this, and what do they already know? |
| Scale | How many, how often, how large? |
| Failure behaviour | What should happen when it goes wrong? |
| Existing system | What must this keep working? |
| Done | How will we know it worked? |

### 3. Sort: ask, assume, or defer

| Kind | Handling |
| --- | --- |
| **Blocking** — wrong answer wastes the work | Ask now, before building |
| **Routine** — a default is obviously fine | Decide, record the assumption |
| **Deferrable** — only matters later | Note it; raise at the step that needs it |

Batch blocking questions into **one** exchange. A drip of single questions is
worse than a considered list, because each round trip costs the requester a
context switch.

### 4. Probe the edges

Most misunderstandings live at the boundaries, not the happy path. For
whatever is being built, ask concretely: what happens with **zero** items,
**one**, **very many**? What if the input is malformed, the network is down,
two people do it at once, or the same request arrives twice?

You do not need answers to all of them. You need to know which ones the
requester has already thought about — that tells you where their real
expectations are.

### 5. Write the spec back

Short, and in their language:

> **Goal:** search results return in under 300ms at p95 for the top 1000
> queries.
> **In scope:** the query path and its index. **Not in scope:** ingestion,
> the admin UI, anything about ranking quality.
> **Assumed:** current traffic (~40 rps) is the ceiling; no new dependencies.
> **Open:** is a stale-by-60s cache acceptable? Blocks the approach.
> **Done when:** the p95 metric holds for 24h under normal traffic.

Getting a *"yes, except…"* on that paragraph is the entire point. It is far
cheaper than getting it on a pull request.

## Anti-patterns

- **The interrogation.** Twenty questions before any thinking. Do the
  thinking first; ask about what remains genuinely undetermined.
- **Silent assumption.** Choosing and not saying. A written assumption gets
  corrected; an unwritten one becomes a defect.
- **Solving in the question.** "Should I use Redis for this?" smuggles a
  design in. Ask about the requirement, decide the mechanism yourself.
- **Accepting a mechanism as a goal.** When someone asks for a specific
  implementation, ask what it is for. Often there is a simpler route.
- **Gold-plating from ambiguity.** Silence is not permission to build the
  configurable, pluggable version.

## When not to use

- The request is already specific and bounded.
- A single obvious edit, where clarifying costs more than doing.
- The requirement is clear and it is the *approach* that is uncertain — that
  is `writing-plans`.
- You are diagnosing a defect: `systematic-debugging`.
