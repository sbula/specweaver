#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Run a list of mutants in one sandbox and file a report you can act on.

`_mutate.py` answers one question at a time, which is the right shape mid-investigation. This asks a
list of them — one detached worktree reused across the batch, `git checkout --` between mutants —
and writes the answers to `.tmp/`, which is gitignored. **Nothing is committed by this tool.**

The report's ordering is the design. Input order is useless; what matters is that the top of the
file is the work:

| Section | Why it is there |
|---|---|
| `SURVIVED` | nothing noticed the behaviour disappearing — the claim is unproven whatever cites it |
| `KILLED x1` | a single point of protection, named. One flaky or skipped test from none |
| `BROKEN` | the mutant did not import, so the run proves nothing — a bad anchor, not a result |
| `KILLED` | genuinely protected. One line each; nothing to act on |

`KILLED x1` is why the default is a full run per mutant rather than `--fast`. Stopping at the first
failure classifies faster but cannot count killers, and the count is the finding: neutralising
`sw check --lineage` orphan detection is caught by exactly one test out of 6840, and that test
failed at `COLUMNS=80` until 2026-08-14 — so the feature was unguarded on any 80-column CI while its
ledger entry looked green. A plain KILLED verdict would have called that healthy.

> [!IMPORTANT]
> **A report is an input to a decision, never a record of one.** Nothing here writes to the proof
> matrix. `AD-1` says the matrix is a document, not a checker, and mutation genuinely needs
> judgement — an *equivalent* mutant, one that does not change observable behaviour, survives for a
> reason that is not a coverage gap. A human copies the conclusion across, or it does not exist.

Campaign file — a JSON list, authored by a human on purpose (generating mutants is `A-VAL-03`):

    [{"file": "src/specweaver/x.py", "old": "a = f()", "new": "a = []",
      "claim": "INT-US-05 C1 — the extractor resolves edges against the worktree"}]

Usage:
    python scripts/_mutate_campaign.py --campaign campaign.json
    python scripts/_mutate_campaign.py --campaign campaign.json --fast --out .tmp/run.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / ".tmp" / "mutation_report.md"

_spec = importlib.util.spec_from_file_location("_mutate", Path(__file__).parent / "_mutate.py")
assert _spec is not None and _spec.loader is not None
_mutate = importlib.util.module_from_spec(_spec)
sys.modules["_mutate"] = _mutate
_spec.loader.exec_module(_mutate)

_REQUIRED = ("file", "old", "new", "claim")


def load_campaign(path: Path) -> list[dict[str, str]]:
    """Parse and validate, so a mutant the runner cannot act on is refused before any sandbox work.

    `claim` is required for the same reason a verdict needs evidence: a `SURVIVED` with no claim
    says a line is unprotected without saying why anyone should care, and the report is unusable.
    """
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not entries:
        raise ValueError(f"campaign is empty: {path}")
    for index, entry in enumerate(entries):
        for key in _REQUIRED:
            if not entry.get(key):
                raise ValueError(f"campaign entry {index} is missing {key!r}")
    return entries


def _bucket(result: dict[str, object]) -> str:
    if result["verdict"] == "SURVIVED":
        return "SURVIVED"
    if result["verdict"] == "BROKEN":
        return "BROKEN"
    return "KILLED x1" if len(result["killers"]) == 1 else "KILLED"


_ORDER = ("SURVIVED", "KILLED x1", "BROKEN", "KILLED")

_BLURB = {
    "SURVIVED": "Nothing objected. The claim is unproven whatever cites it — unless the mutant is "
    "*equivalent*, meaning it does not change observable behaviour. Check that before recording.",
    "KILLED x1": "One test protects this. Not a failure, but one flaky or skipped test from none.",
    "BROKEN": "The mutant did not import, so the run proves nothing. Needs a better anchor.",
    "KILLED": "Genuinely protected. Nothing to act on.",
}


def render_report(results: list[dict[str, object]], meta: dict[str, object]) -> str:
    """The report, ordered by what needs a decision — never by input order."""
    grouped: dict[str, list[dict[str, object]]] = {name: [] for name in _ORDER}
    for result in results:
        grouped[_bucket(result)].append(result)

    minutes, seconds = divmod(int(meta.get("seconds", 0)), 60)
    lines = [
        "# Mutation campaign",
        "",
        f"HEAD `{meta.get('head', '?')}` · tree **{'DIRTY' if meta.get('dirty') else 'CLEAN'}**"
        f" · mode **{meta.get('mode', 'FULL')}** · {len(results)} mutant(s) · {minutes}m{seconds:02d}s",
        "",
        "Not committed, and nothing here writes to the proof matrix — a report is an input to a"
        " decision, never a record of one. Copy conclusions across by hand.",
        "",
        "| bucket | n |",
        "|---|---|",
    ]
    lines += [f"| {name} | {len(grouped[name])} |" for name in _ORDER]
    lines.append(f"| NOT RUN | {meta.get('not_run', 0)} |")
    lines.append("")

    for name in _ORDER:
        rows = grouped[name]
        if not rows:
            continue
        lines += [f"## {name} — {len(rows)}", "", _BLURB[name], ""]
        for row in rows:
            lines.append(f"- **{row['claim']}**")
            lines.append(f"  - `{row['file']}` :: `{row['old']}` → `{row['new']}`")
            if name == "BROKEN" and row.get("detail"):
                lines.append(f"  - {str(row['detail']).strip().splitlines()[-1][:160]}")
            for killer in list(row["killers"])[:12]:
                lines.append(f"  - killed by `{killer}`")
            if len(list(row["killers"])) > 12:
                lines.append(f"  - …and {len(list(row['killers'])) - 12} more")
        lines.append("")

    if meta.get("not_run"):
        lines += [
            f"## NOT RUN — {meta['not_run']}",
            "",
            "Recorded because a report that omits its own gaps reads as *all clear* when it is not.",
            "",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--campaign", required=True, help="JSON list of mutants")
    ap.add_argument(
        "--fast", action="store_true", help="stop at the first failure; loses the killer count"
    )
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="report path (default: .tmp/)")
    ap.add_argument(
        "--tests", default="", help="pytest target for every mutant (default: whole suite)"
    )
    args = ap.parse_args(argv)

    try:
        campaign = load_campaign(Path(args.campaign))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"could not run: {exc}", file=sys.stderr)
        return 2

    head = _mutate._run(["git", "rev-parse", "--short", "HEAD"], REPO_ROOT).strip()
    dirty = bool(_mutate._run(["git", "status", "--porcelain"], REPO_ROOT).strip())

    sandbox = Path(tempfile.mkdtemp(prefix="sw-campaign-"))
    sandbox.rmdir()
    started = time.monotonic()
    results: list[dict[str, object]] = []
    not_run = 0
    try:
        _mutate._build_sandbox(sandbox)
        for index, entry in enumerate(campaign, 1):
            print(f"[{index}/{len(campaign)}] {entry['claim']}", flush=True)
            try:
                result = _mutate.run_one(
                    sandbox,
                    file=entry["file"],
                    old=entry["old"],
                    new=entry["new"],
                    tests=args.tests,
                    fast=args.fast,
                )
            except (ValueError, RuntimeError) as exc:
                result = {"verdict": "BROKEN", "killers": [], "detail": str(exc)}
            finally:
                _mutate.reset_file(sandbox, entry["file"])
            print(f"      {result['verdict']} ({len(result['killers'])} killer(s))", flush=True)
            results.append({**entry, **result})
    except KeyboardInterrupt:
        not_run = len(campaign) - len(results)
        print(f"\ninterrupted — {not_run} mutant(s) not run", file=sys.stderr)
    finally:
        _mutate._run(["git", "worktree", "remove", "--force", str(sandbox)], REPO_ROOT)
        shutil.rmtree(sandbox, ignore_errors=True)

    meta = {
        "head": head,
        "dirty": dirty,
        "mode": "FAST" if args.fast else "FULL",
        "seconds": time.monotonic() - started,
        "not_run": not_run,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(results, meta), encoding="utf-8")
    print(f"\nreport: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
