#!/usr/bin/env bash
# port-check.sh — the "land green" gate for a ported file.
#
# Runs the target language's formatter (check mode), linter / typecheck, and
# a compile-or-syntax gate. Tools that are installed run; tools that are
# missing are reported as SKIP (not FAIL) so the gate is usable on any
# workstation. Exits non-zero if any PRESENT tool reports a problem.
#
# Usage:  port-check.sh <lang> <path...>
#   lang: rust | python | go | cpp | swift | ts | js | ruby | bash
#
# This is Phase 6 of a port (SKILL.md §"Execution plan") made mechanical: a
# port is not done until `port-check.sh <target> <files>` is GREEN.
set -uo pipefail # deliberately not -e: run every check, then aggregate

fail=0
have() { command -v "$1" >/dev/null 2>&1; }
run() { # run "<label>" cmd...
  local label="$1"
  shift
  if "$@" >/tmp/pc.$$ 2>&1; then
    echo "  ✓ $label"
  else
    echo "  ✗ $label"
    sed 's/^/      /' /tmp/pc.$$ | head -20
    fail=1
  fi
  rm -f /tmp/pc.$$
}
skip() { echo "  · $1 — SKIP (not installed)"; }

lang="${1:-}"
shift || true
if [[ -z "$lang" || $# -eq 0 ]]; then
  echo "usage: port-check.sh <lang> <path...>" >&2
  exit 2
fi

echo "port-check [$lang]: $*"
case "$lang" in
rust)
  rustfmt="$(rustup which rustfmt 2>/dev/null || echo rustfmt)"
  clippy="$(rustup which clippy-driver 2>/dev/null || true)"
  run "rustfmt --check" "$rustfmt" --edition 2021 --check "$@"
  for f in "$@"; do
    if [[ -n "$clippy" ]]; then
      td="$(mktemp -d)"
      run "clippy ($f)" "$clippy" --edition 2021 -Dwarnings --emit=metadata --out-dir "$td" --crate-type bin "$f"
      rm -rf "$td"
    else skip "clippy"; fi
    # shellcheck disable=SC2016  # $t/$1 intentionally expand inside the inner bash
    run "rustc --test ($f)" bash -c 't=$(mktemp -u); rustc --edition 2021 --test "$1" -o "$t" && "$t" >/dev/null; r=$?; rm -f "$t"; exit $r' _ "$f"
  done
  ;;
python)
  if have ruff; then
    run "ruff format --check" ruff format --check "$@"
    run "ruff check" ruff check "$@"
  else skip "ruff"; fi
  for f in "$@"; do run "py_compile ($f)" python3 -m py_compile "$f"; done
  ;;
go)
  if have gofmt; then
    unformatted="$(gofmt -l "$@")"
    if [[ -n "$unformatted" ]]; then
      echo "  ✗ gofmt (unformatted: $unformatted)"
      fail=1
    else echo "  ✓ gofmt"; fi
  else skip "gofmt"; fi
  for f in "$@"; do
    if have go; then run "go vet ($f)" go vet "$f"; else skip "go vet"; fi
  done
  ;;
cpp)
  if have clang-format; then run "clang-format" clang-format --dry-run --Werror "$@"; else skip "clang-format"; fi
  for f in "$@"; do run "c++ -std=c++23 -Wall -Wextra ($f)" c++ -std=c++23 -Wall -Wextra -fsyntax-only "$f"; done
  ;;
swift)
  if have swift-format; then run "swift-format lint" swift-format lint --strict "$@"; else skip "swift-format"; fi
  for f in "$@"; do run "swiftc -parse ($f)" swiftc -parse "$f"; done
  ;;
ts)
  if have prettier; then run "prettier --check" prettier --check "$@"; else skip "prettier"; fi
  if have tsc; then run "tsc --noEmit" tsc --noEmit "$@"; else skip "tsc (typecheck — the real TS gate)"; fi
  ;;
js)
  if have prettier; then run "prettier --check" prettier --check "$@"; else skip "prettier"; fi
  if have eslint; then run "eslint" eslint "$@"; else skip "eslint"; fi
  for f in "$@"; do run "node --check ($f)" node --check "$f"; done
  ;;
ruby)
  if have rubocop; then run "rubocop" rubocop "$@"; else skip "rubocop"; fi
  for f in "$@"; do run "ruby -c ($f)" ruby -c "$f"; done
  ;;
bash)
  if have shfmt; then run "shfmt -d" shfmt -d "$@"; else skip "shfmt"; fi
  if have shellcheck; then run "shellcheck" shellcheck "$@"; else skip "shellcheck"; fi
  ;;
*)
  echo "unknown lang: $lang (rust|python|go|cpp|swift|ts|js|ruby|bash)" >&2
  exit 2
  ;;
esac

if [[ $fail -eq 0 ]]; then echo "port-check [$lang]: GREEN"; else echo "port-check [$lang]: RED"; fi
exit "$fail"
