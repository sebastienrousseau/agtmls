#!/usr/bin/env bash
# Reference implementation (SOURCE): dedupe a colon-separated PATH string,
# preserving first occurrence and dropping empty segments.
#
# Contract: one PATH string per stdin line; print the cleaned string per
# line (an all-empty input line yields an empty output line).
#
# THE LANDMINE this port removes: the "obvious" Bash split is
# `for seg in $path` with `IFS=:`, but an unquoted `$path` ALSO undergoes
# pathname (glob) expansion — a segment containing `*` would expand against
# the cwd. The safe idiom is `read -ra` into an array, which splits on IFS
# without globbing. The Python port has neither hazard.
set -euo pipefail

dedupe_path() {
	local path="$1" out="" seen=":" seg
	local -a parts
	IFS=':' read -ra parts <<<"$path"
	for seg in "${parts[@]}"; do
		[[ -z "$seg" ]] && continue
		case "$seen" in
		*":$seg:"*) ;; # already seen — skip
		*)
			out="${out:+$out:}$seg"
			seen="$seen$seg:"
			;;
		esac
	done
	printf '%s\n' "$out"
}

while IFS= read -r line; do
	dedupe_path "$line"
done
