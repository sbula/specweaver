#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Census every gate-bypass in the repo and ratchet it — the count may fall, never rise.

Why this exists. For a human author a `# noqa` is laziness. For an agent working under a gate,
adding the suppression is the CHEAPEST CORRECT SOLUTION to the stated constraint: strictly less
work than fixing the code, and it satisfies the gate exactly. Every other check in this runner is
only as strong as this one, because every other check can be switched off one line at a time.

Measured on this repo when the ratchet was written (2026-07-28): 121 inline `noqa`, 105
`type: ignore`, 2 `pragma: no cover`. `ruff check src/` exits 0; `ruff check src/ --ignore-noqa`
returns 121 errors, 20 of them C901 — including `decompose.py::execute` at complexity 30 against
a limit of 10.

CONFIG-LEVEL suppressions are counted too, and that is not padding. Adding one
`per-file-ignores` entry to `pyproject.toml` silences a whole file in a single line — strictly
cheaper than the inline comments it replaces, and invisible to any checker that only greps for
`noqa`. A ratchet with that hole in it measures diligence, not exposure.

Policy: a FROZEN BASELINE, failing only on growth. Assumed rather than instructed (user has not
yet chosen between this and fail-at-zero) because with 228 suppressions already live, a
fail-at-zero gate is red from its first run and would simply be ignored. Re-freeze deliberately
with `--update-baseline`; the diff is then reviewable in git, which is the point.

Not every suppression is debt. Of the 121 inline `noqa`, ~40 are `N802` on deliberately
uppercase abstract properties (`SCM_SKELETON_QUERY`) in `workspace/ast/parsers/`, and ~17 are
`F401` on import-for-side-effect registries. Those are rules misconfigured for one package, and
the honest fix is config, not code. The census exists to make that distinction visible before it
is frozen.

Exit 1 if any category exceeds its baseline.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
import tomllib
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "scripts" / "baselines" / "suppressions.json"

#: Gated trees. `tests/` is censused for visibility but not ratcheted — test files carry a
#: deliberate TID251 blanket exemption, so mixing them in would drown the production signal.
GATED_TREES = ("src", "scripts")
REPORTED_TREES = ("tests",)

_NOQA = re.compile(r"#\s*noqa(?::\s*(?P<codes>[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*))?", re.I)
_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?:\[(?P<codes>[^\]]*)\])?")
_PRAGMA = re.compile(r"#\s*pragma:\s*no\s*cover")
_MYPY_FILE = re.compile(r"#\s*mypy:\s*ignore-errors")


def _iter_py(trees: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    for tree in trees:
        root = REPO_ROOT / tree
        if root.is_dir():
            found.extend(p for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts)
    return found


def _comments(source: str) -> list[str]:
    """Yield only real comment tokens.

    Scanning raw lines counts the word `noqa` wherever it appears — including inside this file's
    own docstring and detection regexes, which is how the first run reported a blanket `noqa`
    that does not exist. A checker that miscounts itself cannot be trusted about anything else.
    Falls back to raw lines only if the file will not tokenize.
    """
    try:
        return [
            tok.string
            for tok in tokenize.generate_tokens(io.StringIO(source).readline)
            if tok.type == tokenize.COMMENT
        ]
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return source.splitlines()


def scan_source(source: str) -> Counter[str]:
    """Count every inline suppression in one file, keyed by category:code."""
    counts: Counter[str] = Counter()
    for line in _comments(source):
        if (m := _NOQA.search(line)) is not None:
            codes = m.group("codes")
            if codes:
                for code in (c.strip().upper() for c in codes.split(",")):
                    counts[f"noqa:{code}"] += 1
            else:
                counts["noqa:BLANKET"] += 1
        if (m := _TYPE_IGNORE.search(line)) is not None:
            codes = m.group("codes")
            if codes and codes.strip():
                for code in (c.strip() for c in codes.split(",")):
                    counts[f"type-ignore:{code}"] += 1
            else:
                # PGH003 territory: a blanket ignore hides every future error on that line too.
                counts["type-ignore:BLANKET"] += 1
        if _PRAGMA.search(line):
            counts["pragma:no-cover"] += 1
        if _MYPY_FILE.search(line):
            counts["mypy:file-ignore-errors"] += 1
    return counts


def scan_config() -> Counter[str]:
    """Count suppressions declared in pyproject.toml rather than in the code."""
    counts: Counter[str] = Counter()
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.is_file():
        return counts

    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    ruff = data.get("tool", {}).get("ruff", {}).get("lint", {})

    for codes in ruff.get("per-file-ignores", {}).values():
        for code in codes:
            counts[f"config:per-file-ignore:{code}"] += 1

    for code in ruff.get("ignore", []):
        counts[f"config:ruff-ignore:{code}"] += 1

    for override in data.get("tool", {}).get("mypy", {}).get("overrides", []):
        if override.get("ignore_errors") or override.get("ignore_missing_imports"):
            counts["config:mypy-override"] += 1

    return counts


def census(trees: tuple[str, ...]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in _iter_py(trees):
        try:
            counts.update(scan_source(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return counts


def load_baseline() -> dict[str, int] | None:
    if not BASELINE_PATH.is_file():
        return None
    return dict(json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["counts"])


def write_baseline(counts: Counter[str]) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(
            {
                "_comment": (
                    "Frozen suppression baseline. Regenerate ONLY with "
                    "`python scripts/check_suppressions.py --update-baseline`, and expect the "
                    "diff to be reviewed: every increase is a gate someone switched off."
                ),
                "counts": dict(sorted(counts.items())),
                "total": sum(counts.values()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def compare(current: Counter[str], baseline: dict[str, int]) -> list[tuple[str, int, int]]:
    """Return (category, baseline, current) for every category that grew."""
    return [
        (key, baseline.get(key, 0), value)
        for key, value in sorted(current.items())
        if value > baseline.get(key, 0)
    ]


def _print_census(counts: Counter[str], title: str) -> None:
    if not counts:
        print(f"{title}: none")
        return
    print(f"{title}: {sum(counts.values())} total")
    for key, value in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {value:>4}  {key}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "paths",
        nargs="*",
        help="ignored — the ratchet is inherently repo-wide (a suppression anywhere counts)",
    )
    ap.add_argument("--update-baseline", action="store_true", help="re-freeze the baseline")
    ap.add_argument("--census-only", action="store_true", help="report counts, never fail")
    args = ap.parse_args(argv)

    gated = census(GATED_TREES)
    gated.update(scan_config())
    reported = census(REPORTED_TREES)

    if args.update_baseline:
        write_baseline(gated)
        _print_census(gated, "Suppression baseline frozen")
        print(f"\nWrote {BASELINE_PATH.relative_to(REPO_ROOT).as_posix()}")
        return 0

    _print_census(gated, f"Suppressions in {'/, '.join(GATED_TREES)}/ (gated)")
    print()
    _print_census(reported, f"Suppressions in {'/, '.join(REPORTED_TREES)}/ (reported only)")

    if args.census_only:
        return 0

    baseline = load_baseline()
    if baseline is None:
        print(
            f"\nBLOCKED: no baseline at {BASELINE_PATH.relative_to(REPO_ROOT).as_posix()}.\n"
            "Freeze the current state with:\n"
            "    python scripts/check_suppressions.py --update-baseline\n"
            "Sort the config-category entries FIRST (see this file's docstring) — whatever is "
            "frozen becomes permanent."
        )
        return 1

    grown = compare(gated, baseline)
    if not grown:
        total, frozen = sum(gated.values()), sum(baseline.values())
        drop = f", {frozen - total} fewer than baseline" if total < frozen else ""
        print(f"\nSuppression ratchet: {total} at or below baseline {frozen}{drop}")
        return 0

    print("\nBLOCKED: suppressions grew past the frozen baseline\n")
    for key, was, now in grown:
        print(f"    {key}: {was} -> {now}  (+{now - was})")
    print(
        "\nFix the code the gate objected to. If the rule is genuinely wrong for this package, "
        "change the rule's configuration (reviewable, one place) rather than suppressing at the "
        "call site — then re-freeze with --update-baseline."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
