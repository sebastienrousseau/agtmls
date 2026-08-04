---
name: receiving-code-review
description: "Respond to review feedback on your own change without reflexively complying or reflexively defending. Load when a reviewer leaves comments, requests changes, or disagrees with an approach, and when deciding whether to argue a point or accept it. Every comment gets a decision and a reply; silent edits and silent skips are the failure modes. Not preparing or shipping the change itself."
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

# Receiving code review

**Trigger.** A reviewer — human or agent — has left comments on your change:
inline notes, a change request, a design objection, or a question you are not
sure how to answer.

> **Reference material** (comment triage table with worked replies, handling
> a reviewer who is wrong, scope-creep boundaries, and review of
> agent-authored changes): see `reference.md` in this directory.

## The rule

> **Every comment gets a decision and a reply. Disagreement is fine; silence
> is not.**

Two symmetrical failures, and the second is the one people underestimate:

- **Reflexive compliance.** Making every requested change without evaluating
  it. Reviewers are frequently right and occasionally wrong, and a change you
  made without agreeing with it is a change nobody understands. Worse, "done"
  on a request you misread produces a defect with a reviewer's name on it.
- **Reflexive defence.** Explaining why each comment is unnecessary. This
  converts review into negotiation and costs you the thing review is for.

The correct posture is neither: **evaluate, decide, and say what you decided.**

## Triage every comment

Classify before responding. The category determines the reply.

| Category | What it is | Response |
| --- | --- | --- |
| **Defect** | The code is wrong; reviewer showed how | Fix, verify, reply with the evidence |
| **Risk** | Not wrong today, fragile tomorrow | Fix, or record why the risk is accepted |
| **Design** | A different approach is preferred | Engage on merits; one of you updates |
| **Preference** | Style with no correctness content | Accept by default — it is their codebase too |
| **Question** | Reviewer does not understand something | Answer; then ask if the *code* should have |
| **Misunderstanding** | Reviewer read it wrong | Clarify, and check what misled them |

Two rules that fall out of this table:

- **Accept preferences cheaply.** Arguing naming or formatting spends
  credibility you will want for a design disagreement later.
- **A question is a signal.** If a reviewer had to ask what the code does,
  the answer usually belongs in the code — a name, a comment, a test — not
  only in the reply thread.

## Working the feedback

1. **Read everything first.** Do not start editing on comment one. Later
   comments frequently reframe earlier ones, and a reviewer's last note may
   say "actually, ignore the above."
2. **Group by category and by file.** Related fixes land together and are
   easier to re-review.
3. **Make the changes.** Each one is a real change: verify it as you would
   any other. A fix applied to satisfy a comment, untested, is a regression
   with extra steps.
4. **Re-run the full gate**, not the file you touched. Review fixes break
   other things at roughly the rate original changes do.
5. **Reply to each thread** with what you did — or did not do, and why.

## Replying

Say the decision, then the evidence. Keep it short.

**Fixed:**

> Fixed in `parser.py:88` — the split now bounds on the first colon only.
> `test_config_key_with_colon` covers it; it failed before the change.

**Disagreeing:**

> I'd rather keep the loop here. `itertools.groupby` requires the input to be
> pre-sorted and this iterator is streaming, so we'd add an O(n log n) sort
> and buffer the whole stream to save four lines. Happy to change it if you
> still prefer the shorter form.

That is the shape: a reason grounded in something checkable, and an explicit
willingness to be overruled. Compare with "I think this is clearer", which
is an assertion the reviewer cannot evaluate.

**Deferring:**

> Agreed, but out of scope for this change — it touches the v1 handlers I
> deliberately excluded. Filed as #412.

Deferring is legitimate **only** with a record. "Later" without a ticket is
"never" with better manners.

## Scope discipline

The pull to fix adjacent things while you are in the file is strong and
almost always wrong. It grows the diff, buries the reviewed change, and
restarts the review.

- Unrelated bug spotted → separate change.
- Reviewer asks for something beyond the stated scope → say so, agree where
  it belongs, do it there.
- Refactor that would make the fix cleaner → land the fix, then the refactor,
  in that order and separately.

## When not to use

- You are *giving* review, not receiving it.
- You are preparing the change, checking CI, or writing release notes —
  that is the project's PR and release workflow.
- The project defines its own review protocol or approval rules; follow it.
