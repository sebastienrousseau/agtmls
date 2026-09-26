#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Atheris (libFuzzer) harness for the targets in targets.py.

    python3 fuzz/fuzz.py <target> [libFuzzer options] [corpus dir]
    python3 fuzz/fuzz.py json_escapes -max_total_time=60 fuzz/corpus/json_escapes

Atheris ships Linux x86_64 wheels only; CI runs this in fuzz.yml. Elsewhere,
tests/test_fuzz_targets.py replays the same targets without it.
"""

import sys

import atheris

with atheris.instrument_imports():
    from targets import TARGETS

if len(sys.argv) < 2 or sys.argv[1] not in TARGETS:
    sys.exit(f"usage: fuzz.py <{'|'.join(TARGETS)}> [libFuzzer options]")
target = TARGETS[sys.argv.pop(1)]
atheris.Setup(sys.argv, target)
atheris.Fuzz()
