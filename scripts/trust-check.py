#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""One signature, advisory or attestation, for the agtmls-spec conformance runner.

`agtmls verify` judges an install against this registry's own index and
feed. The spec's vectors are other files, at fixed verification times, so
the runner asks for one judgement at a time instead:

    trust-check.py signature <file> --sig <file> --allowed-signers <file> \
        --namespace <ns> [--verify-time YYYYMMDD] [--json]
    trust-check.py advisories <feed> --allowed-signers <file> --lockfile <file> \
        [--sig <file>] [--verify-time YYYYMMDD] [--json]
    trust-check.py attest <manifest|capabilities> <skill-dir> --name <skill> \
        [--digest sha256:<hex>]

Flags, JSON and exit codes match agtmls-rs's `signature`, `advisories` and
`attest` subcommands, so the runner can compare the two implementations
directly. `attest` prints the canonical statement (spec 10.2), judged by
this checkout's pinned rule snapshot. Exit codes:
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
from _lib import (  # noqa: E402  (needs the scripts path first)
    advisories,
    attestations,
    signatures,
)
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


def attest(args: argparse.Namespace) -> int:
    if not args.dir.is_dir():
        print(f"error: {args.dir} is not a directory", file=sys.stderr)
        return EXIT_ERROR
    if args.kind == "manifest":
        statement = attestations.manifest_statement(args.name, args.dir)
    else:
        statement = attestations.capabilities_statement(args.name, args.dir, args.digest)
    sys.stdout.write(attestations.render(statement))
    return EXIT_OK


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
    statement = commands.add_parser("attest", help="print one attestation")
    statement.add_argument("kind", choices=["manifest", "capabilities"])
    statement.add_argument("dir", type=Path)
    statement.add_argument("--name", required=True)
    statement.add_argument("--digest")
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
        handler = {"signature": signature, "advisories": advisory, "attest": attest}[args.command]
        return handler(args)
    except (signatures.ToolMissing, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
