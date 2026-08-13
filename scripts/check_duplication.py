#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Copy-paste detection, ratcheted. `TECH-037`.

Nothing in this repo looked for duplicated code until 2026-08-12. Every instance fixed that day was
found by ACCIDENT while reading code for something else -- `_is_symbol_valid` written out four
times (three byte-identical), the `log_artifact_event` tail seven times, `_build_run_context` twice
at forty lines each. Two of them were live defects rather than mere repetition: the hand-rolled
artifact-tag reader that made `sw lineage tree spec.md` silently resolve nothing, and the copy of
the lineage tail that was missing its `None` guard.

**Detection is `jscpd`'s, not ours.** `ruff` cannot do this -- 115 Pylint rules are implemented and
`R0801` is not among them. A stdlib AST checker was prototyped and rejected: it compares whole
functions, so a block duplicated INSIDE two differently-shaped functions is invisible to it, and
jscpd finds those.

**The ratchet is ours, and the key is the point.** jscpd reports line ranges, which move whenever
anything above them changes; a baseline keyed on those would report a false regression for almost
every commit and be re-frozen until nobody read it. So a clone is identified by its TEXT plus the
pair of files it spans. Adding a clone blocks; removing one never does.

jscpd's own `--threshold` is deliberately NOT used: it compares an aggregate percentage, and the
planted-regression probe moved that by 5 lines in 2168 -- 0.01pp. Any commit that also removed five
duplicated lines would mask it, and removing forty in one commit is something this repo has
actually done.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE = REPO_ROOT / "scripts" / "baselines" / "duplication.json"

#: Below this, jscpd reports import blocks and boilerplate signatures as clones. Load-bearing:
#: tuning it down surfaces per-language parser code where the differing CONSTANTS are the point,
#: which is the false-positive class that gets a check suppressed rather than acted on.
MIN_TOKENS = 50

#: Duplication is inherently cross-file: a clone's twin may sit in a file the commit never touched.
#: A `changed` scope therefore cannot see it, which is exactly how `check_class_health` stayed
#: invisible for a whole session. This check always reads the whole tree.
TREES = ("src",)


def clone_key(duplicate: dict) -> str:
    """A clone's identity: the file pair it spans, plus a hash of the duplicated text.

    Independent of line numbers by construction. Whitespace-normalised so re-indenting a block --
    moving it into a method, say -- does not read as a new clone.
    """
    body = "\n".join(line.strip() for line in duplicate["fragment"].splitlines() if line.strip())
    first, second = sorted([duplicate["firstFile"]["name"], duplicate["secondFile"]["name"]])
    digest = hashlib.sha1(body.encode("utf-8")).hexdigest()[:12]
    return f"{first} <-> {second} @{digest}"


def clones_from(duplicates: list[dict]) -> dict[str, dict]:
    """`{clone key: {lines, first, second}}` for a list of jscpd duplicate records."""
    return {
        clone_key(d): {
            "lines": d["lines"],
            "first": f"{d['firstFile']['name']}:{d['firstFile']['start']}",
            "second": f"{d['secondFile']['name']}:{d['secondFile']['start']}",
        }
        for d in duplicates
    }


def load_report(report: Path) -> dict[str, dict]:
    """Read a `jscpd-report.json` into keyed clones."""
    return clones_from(json.loads(report.read_text(encoding="utf-8"))["duplicates"])


def new_clones(current: dict[str, dict], frozen: dict[str, dict]) -> list[str]:
    """Clone keys present now and absent from the baseline. Removals are never regressions."""
    return sorted(set(current) - set(frozen))


def run_jscpd(paths: list[str], out_dir: Path, *, jscpd: str, min_tokens: int) -> Path | None:
    """Run jscpd into `out_dir`; return the report path, or None if it could not run.

    Tries the local cache first so a commit gate does not need the network. `--yes` is the fallback
    for a machine that has never fetched it.
    """
    base = [
        "--min-tokens",
        str(min_tokens),
        "--format",
        "python",
        "--silent",
        "--reporters",
        "json",
        "--output",
        str(out_dir),
        *paths,
    ]
    for prefix in (["npx", "--offline", jscpd], ["npx", "--yes", jscpd]):
        if shutil.which(prefix[0]) is None:
            return None
        try:
            subprocess.run([*prefix, *base], check=False, capture_output=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired):
            continue
        report = out_dir / "jscpd-report.json"
        if report.is_file():
            return report
    return None


def _measure(paths: list[str], *, jscpd: str, min_tokens: int) -> dict[str, dict] | None:
    with tempfile.TemporaryDirectory() as tmp:
        report = run_jscpd(paths, Path(tmp), jscpd=jscpd, min_tokens=min_tokens)
        return load_report(report) if report else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", help="trees to scan (default: src)")
    ap.add_argument("--baseline", default=str(BASELINE))
    ap.add_argument("--jscpd", default="jscpd@4", help="npx package spec for the detector")
    ap.add_argument("--min-tokens", type=int, default=MIN_TOKENS)
    ap.add_argument("--report", help="read an existing jscpd-report.json instead of running it")
    ap.add_argument(
        "--update-baseline",
        action="store_true",
        help="rewrite the baseline from the current tree; the diff is meant to be reviewed",
    )
    args = ap.parse_args(argv)

    paths = args.paths or [str(REPO_ROOT / t) for t in TREES]

    if args.report:
        # An unreadable report is the same situation as a detector that would not start: nothing
        # was measured. It must not fall through to "no new clones".
        try:
            current: dict[str, dict] | None = load_report(Path(args.report))
        except (OSError, ValueError, KeyError):
            current = None
    else:
        current = _measure(paths, jscpd=args.jscpd, min_tokens=args.min_tokens)

    if current is None:
        # NOT a pass. `quality.py` grades a missing tool as MISSING, which counts as failed, and
        # this is the same situation: nothing was verified.
        print(
            "FAIL  could not run the duplication detector "
            f"({args.jscpd} via npx). A check that cannot run is not a check that passed."
        )
        return 2

    baseline_path = Path(args.baseline)
    if args.update_baseline:
        baseline_path.write_text(json.dumps(dict(sorted(current.items())), indent=2) + "\n")
        print(f"Duplication baseline written: {len(current)} clone(s)")
        return 0

    if not baseline_path.is_file():
        print(
            f"FAIL  no duplication baseline at {baseline_path} — run "
            "`python scripts/check_duplication.py --update-baseline`. Without one every clone "
            "reads as frozen."
        )
        return 2

    frozen = json.loads(baseline_path.read_text(encoding="utf-8"))
    added = new_clones(current, frozen)

    gone = sorted(set(frozen) - set(current))
    if gone:
        print(f"{len(gone)} clone(s) removed — re-freeze with --update-baseline:")
        for key in gone[:8]:
            print(f"    {key}")
        print()

    if not added:
        print(f"Duplication ratchet: {len(current)} clone(s), none new")
        return 0

    print(f"NEW duplication ({len(added)} clone(s)):\n")
    for key in added:
        entry = current[key]
        print(f"  {entry['lines']:3d} lines  {entry['first']}")
        print(f"             <-> {entry['second']}")
    print("\nExtract the shared code, or re-freeze deliberately if the repetition is the point.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
