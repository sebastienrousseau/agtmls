#!/usr/bin/env bash
# Boundary trap (reference.md §R4): a u64 above 2^53 loses precision when it
# crosses a seam as a JSON *number* (JS/JSON numbers are f64), but survives
# as a JSON *string*. Proves the trap BITES and the string contract CATCHES
# it. This is the exact trap noyalib's `lossless-u64` feature exists to
# defeat — every Python/Rust/Go <-> JS/JSON port inherits it.
set -euo pipefail
cd "$(dirname "$0")"

VAL=9007199254740993 # 2^53 + 1

# shellcheck disable=SC2016  # ${s} is a JS template literal, not bash
got_number=$(node -e 'const s=process.argv[1]; process.stdout.write(String(JSON.parse(`{"id":${s}}`).id))' "$VAL")
# shellcheck disable=SC2016  # ${s} is a JS template literal, not bash
got_string=$(node -e 'const s=process.argv[1]; process.stdout.write(JSON.parse(`{"id":"${s}"}`).id)' "$VAL")

echo "original:        $VAL"
echo "as JSON number:  $got_number   <- JS f64, the trap"
echo "as JSON string:  $got_string   <- the contract"

fail=0
if [[ "$got_number" == "$VAL" ]]; then
  echo "UNEXPECTED: number form kept precision (env-specific?)" >&2
  fail=1
else
  echo "✓ trap bites: number form drifted ($VAL -> $got_number)"
fi
if [[ "$got_string" != "$VAL" ]]; then
  echo "FAIL: string contract did not preserve the value" >&2
  fail=1
else
  echo "✓ contract holds: string form preserved $VAL"
fi
exit "$fail"
