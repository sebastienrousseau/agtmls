# Language profile: Bash/Shell

You are working in a Bash/Shell project. The universal rules above
still apply; this section refines them for shell idioms.

## Safety header

- Every script opens with `#!/usr/bin/env bash` followed
  immediately by `set -euo pipefail` as the first line of the body
  — no exceptions without a comment explaining why a flag is
  unsafe for this script.
- Set `IFS` deliberately whenever you rely on word-splitting
  (`IFS=$'\n\t'` or a loop-local `IFS=,`); don't depend on the
  ambient default.
- Use `trap '...' ERR` for diagnostics and `trap '...' EXIT` for
  cleanup (temp files, background jobs, lock files) so cleanup runs
  on both success and failure paths.
- `set -x` is a debugging aid, not a shipped behaviour — gate it
  behind a `DEBUG`/`TRACE` env var, don't leave it on by default.

## Quoting & expansion (the landmine section)

- ALWAYS quote expansions: `"$var"`, `"${arr[@]}"`,
  `"$(command)"`. An unquoted `$var` undergoes word-splitting AND
  pathname expansion — both are bugs waiting for a filename with a
  space or a glob character.
- Use arrays for anything that is conceptually a list (file paths,
  command arguments), never a space-joined string you split later.
  `"${files[@]}"` in a loop or as command arguments; `"${files[*]}"`
  only when you explicitly want one joined string.
- `[[ ]]` over `[ ]` for conditionals — no word-splitting/globbing
  on its operands, and it supports `&&`, `||`, `=~` natively.
- `read -ra arr <<< "$line"` to split input into an array without
  triggering globbing; bare `$(cmd)` assigned unquoted is the same
  trap as an unquoted variable.
- Never parse `ls` output. Use globs, `find -print0` piped to
  `xargs -0` or a `while IFS= read -r -d ''` loop, or (bash 4+)
  `shopt -s nullglob` with a plain glob.
- `$?` reflects the last command's exit status — after a pipeline,
  that's the *last stage* unless `set -o pipefail` is on. Without
  `pipefail`, `cmd_that_fails | grep x` reports success. Turn it on
  in the safety header, and know it's already implied there.

## Error handling

- `set -e` does NOT fire inside `if`, `while`, `&&`/`||` chains, or
  command substitution assigned to a variable — check exit codes
  explicitly in those positions: `if ! cmd; then ...; fi`, or
  `cmd || { rc=$?; ...; }`.
- Prefer functions that `return` a meaningful exit code over
  functions that set a global status variable.
- Declare function-local variables with `local` (or `local -a` for
  arrays); leaking names into the caller's scope is a bug.
- Validate inputs at the top of a function or script — unset
  positional args, empty strings, and paths that don't exist are
  the common failure modes. Fail loudly with a message on stderr
  and a non-zero exit, not a silent no-op.
- Never `eval` on untrusted input, and treat any `eval` as a design
  smell — there is almost always a `printf -v`, array, or
  `"${!name}"` indirect-expansion alternative.

## Idioms

- Wrap reusable logic in functions with `local` variables; a script
  that's more than a linear sequence of commands should have a
  `main` function called at the bottom, after all functions are
  defined.
- `printf '%s\n' "$var"` over `echo` for anything that might contain
  a leading `-`, a backslash escape, or an unquoted expansion —
  `echo` behaviour for escapes is not portable across shells.
- `mktemp` for temp files/dirs, paired with a `trap ... EXIT` that
  removes them — never a hardcoded path under `/tmp`.
- `"$(...)"` command substitution over backticks — backticks nest
  poorly and quote awkwardly.
- Parameter expansion over spawning an external process:
  `${var:-default}`, `${var:?error message}`, `${var%suffix}`,
  `${var#prefix}`, `${var//search/replace}` beat a `sed`/`awk` pipe
  for simple string work.
- `cd "$(git rev-parse --show-toplevel)"` (or an explicit absolute
  path) at the top of a script that assumes repo-root-relative
  paths, rather than trusting the caller's cwd.

## Portability

- State explicitly, at the top of the script, whether it targets
  bash (`#!/usr/bin/env bash`) or POSIX `sh` (`#!/bin/sh`). Don't
  let a script drift between the two.
- If the shebang is `#!/bin/sh`, avoid bashisms: no arrays, no
  `[[ ]]`, no `local` (unless the target `sh` is known to be dash
  with `local` support — don't assume), no `${var,,}`/`${var^^}`
  case conversion, no `<<<` here-strings, no `function` keyword.
  When in doubt, target bash explicitly instead of writing
  bash-flavoured `sh`.

## Testing discipline

- Non-trivial scripts (anything with branching, multiple functions,
  or side effects worth protecting) get a `bats` test suite.
- Test the observable contract: stdout content, stderr content
  where it matters, and exit code — not internal implementation
  details like which helper function ran.
- A bug fix ships with a test that fails on the pre-fix script and
  passes after, in the same commit.

## Toolchain

CI already enforces `shellcheck` and `shfmt`; run them before
pushing and pass the gate rather than re-describing it. The
conventions the linter can't express for you:

- A `shellcheck` warning you disagree with gets a narrowly-scoped
  `# shellcheck disable=SCxxxx` directly above the line, with a
  comment explaining why it's a false positive here — never a
  blanket `disable` at the top of the file.
- `shfmt` formats to 2-space indent to match house style
  (`shfmt -i 2 -w`); don't hand-format around it.
- Quote style, brace style, and indent are `shfmt`'s job — spend
  review time on logic, not whitespace.

## What NOT to do

- No unquoted expansions — `$var` instead of `"$var"` is a bug
  report waiting to happen, not a style preference.
- No parsing `ls` output.
- No `eval` on anything that touches user input, environment
  variables from an untrusted source, or network responses.
- No relying on `set -e` inside a pipeline, an `if`/`while`
  condition, or a command-substitution assignment without
  understanding those are the documented exceptions — check the
  exit code explicitly there.
- No reaching for a 300-line shell script once you need real data
  structures, structured error handling, or non-trivial control
  flow — that's a job for Python or Rust; use the
  `cross-language-port` skill to move it rather than bolting more
  logic onto a shell script.
