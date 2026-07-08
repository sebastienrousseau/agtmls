---
name: cross-language-port
description: |
  Autonomously translate a module, script, or function from one
  programming language to another while preserving business logic
  and adopting idiomatic patterns of the target language. Load when
  the user asks to "port this", "translate to <language>", "rewrite
  in <language>", or "convert this to <language>".
---

# Skill: cross-language porting

**Trigger.** The user asks to *port this*, *translate to [Language]*,
or *rewrite in [Language]*.

## Objective

Autonomously translate a specific module, script, or function from
one programming language to another while preserving exact business
logic, but adopting the idiomatic features of the target language.

## Execution plan

1. **Source analysis.** Read the provided source file. Identify the
   core algorithm, dependencies, IO operations, and edge-case
   handling.
2. **Idiom mapping.** Determine the correct standard-library
   equivalents in the target language.
    - Python `requests` → Rust `reqwest`.
    - C++ `std::thread` → Go goroutines.
    - JS `Promise.all` → Python `asyncio.gather`.
3. **Translation.** Write the new code in the target language.
    - Do NOT do a literal 1:1 line translation.
    - Rewrite the logic so it looks like it was originally written by
      a senior developer of the target language.
4. **Test generation.** Write a suite of unit tests in the target
   language that verifies the new code produces the exact same
   outputs as the original source code.
5. **Output.** Provide the fully ported file and the accompanying
   tests.

## When NOT to use

- **Micro-porting** (translating a single function of a few lines)
  — do it inline in the conversation without invoking this skill.
- **Rewrites that change behaviour** — that's a redesign, not a
  port. Ask the user to clarify the target behaviour first.
