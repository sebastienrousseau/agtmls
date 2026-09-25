#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""One signature or advisory judgement, for the agtmls-spec conformance runner.

`agtmls verify` judges an install against this registry's own index and
feed. The spec's vectors are other files, at fixed verification times, so
the runner asks for one judgement at a time instead:

    trust-check.py signature <file> --sig <file> --allowed-signers <file> \
        --namespace <ns> [--verify-time YYYYMMDD] [--json]
    trust-check.py advisories <feed> --allowed-signers <file> --lockfile <file> \
        [--sig <file>] [--verify-time YYYYMMDD] [--json]

Flags, JSON and exit codes match agtmls-rs's `signature` and `advisories`
subcommands, so the runner can compare the two implementations directly:
0 verified or clean, 4 unsigned, 5 bad signature, 6 revoked, 1 when
nothing could be concluded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import advisories, signatures  # noqa: E402  (needs the scripts path first)
from _lib.lockfile import (  # noqa: E402  (same)
    EXIT_BAD_SIGNATURE,
    EXIT_ERROR,
    EXIT_OK,
    EXIT_REVOKED,
    EXIT_UNSIGNED,
)

STATUS_EXIT = {"verified": EXIT_OK, "bad_signature": EXIT_BAD_SIGNATURE, "unsigned": EXIT_UNSIGNED}


def signature(args: argparse.Namespace) -> int:
    status = signatures.verify(args.file, args.sig, args.allowed_signers, args.namespace,
                               verify_time=args.verify_time)
    print(json.dumps({"status": status}) if args.json else status)
    return STATUS_EXIT[status]


def advisory(args: argparse.Namespace) -> int:
    sig = args.sig or args.file.with_name(args.file.name + ".sig")
    status = signatures.verify(args.file, sig, args.allowed_signers, signatures.ADVISORY_NAMESPACE,
                               verify_time=args.verify_time)
    lock = json.loads(args.lockfile.read_text(encoding="utf-8"))
    hits = (advisories.revoked(json.loads(args.file.read_text(encoding="utf-8")), lock)
            if status == "verified" else [])
    revoked = [{"skill": n, "digest": d, "advisories": ids} for n, d, ids in hits]
    if args.json:
        print(json.dumps({"advisory_feed": status, "revoked": revoked}))
    else:
        print(status)
        for hit in revoked:
            print(f"REVOKED {hit['skill']}  {hit['digest']} by {', '.join(hit['advisories'])}")
    if status == "bad_signature":
        return EXIT_BAD_SIGNATURE
    return EXIT_REVOKED if hits else STATUS_EXIT[status]


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = top.add_subparsers(dest="command", required=True)
    one = commands.add_parser("signature", help="verify one signature")
    one.add_argument("file", type=Path)
    one.add_argument("--sig", type=Path, required=True)
    one.add_argument("--namespace", required=True)
    feed = commands.add_parser("advisories", help="judge a feed against a lockfile")
    feed.add_argument("file", type=Path)
    feed.add_argument("--lockfile", type=Path, required=True)
    feed.add_argument("--sig", type=Path)
    for sub in (one, feed):
        sub.add_argument("--allowed-signers", type=Path, required=True)
        sub.add_argument("--verify-time", type=verify_time)
        sub.add_argument("--json", action="store_true")
    return top


def verify_time(value: str) -> str:
    if not signatures.is_verify_time(value):
        raise argparse.ArgumentTypeError(f"{value!r} is not YYYYMMDD")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return signature(args) if args.command == "signature" else advisory(args)
    except (signatures.ToolMissing, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
