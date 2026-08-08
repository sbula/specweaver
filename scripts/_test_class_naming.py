#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""R6: a unit test class names the class or function it exercises.

Split out of `scripts/check_conventions.py` (2026-08-08), which had no headroom under the file-size
ceiling — the same reason `_refactor_diff_safety.py` and `_story_resolution.py` were split off
`tests.py`. The seam is real rather than convenient: R1-R5 judge one file at a time and report
violations, while R6 is a repo-wide census compared against a frozen baseline. Different shape,
different output, different scope.

Matched in BOTH directions, because both occur legitimately. `TestToolRegistry` *contains* its
symbol; `TestRegistryIdsInNames` is *contained by* `check_registry_ids_in_names` — the `check_`
prefix is not part of the subject, and every gate script in this repo is named that way. One-way
matching gets all of them wrong, which is how the first draft of this rule would have rejected the
test class written for it.

Ratcheted rather than enforced outright: several hundred existing classes group by behaviour
instead — too many, and too many of them judgement calls, to sweep in one go. The count per test
directory may fall, never rise.
"""

from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

BASELINE_PATH = REPO_ROOT / "scripts" / "baselines" / "test_class_naming.json"

#: A stem shorter than this may not qualify by being *contained in* a symbol.
#:
#: Measured, not chosen. `Get` is contained by 99 real symbols, `Run` by 76, `Add` by 22 — so
#: `TestGet` passes by accident. An empty stem (`class Test:`) is contained by every symbol and
#: passes vacuously. Both fail OPEN: the census reports a healthy number while accepting the least
#: informative names there are. Tested at 0/5/6/8; 5 is the least restrictive value that rejects
#: `Get`/`Add`/`Tag` while keeping every legitimate name. The other direction — a symbol contained
#: in the stem — needs no guard, since symbols are already filtered to more than 3 characters.
MIN_CONTAINED_STEM = 5


def source_symbols(repo_root: Path = REPO_ROOT) -> set[str]:
    """Every class and function defined under `src/` and `scripts/`, in CamelCase.

    Functions are camelised here so callers can compare `is_fixture_data` with
    `TestIsFixtureData` without repeating the conversion.
    """
    symbols: set[str] = set()
    for tree in ("src", "scripts"):
        for path in (repo_root / tree).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                parsed = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            for node in ast.walk(parsed):
                if isinstance(node, ast.ClassDef):
                    symbols.add(node.name)
                elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    symbols.add("".join(w.title() for w in node.name.strip("_").split("_")))
    return {s for s in symbols if len(s) > 3}


def class_names_subject(stem: str, symbols: set[str]) -> bool:
    """Whether a unit test class stem names the class or function it exercises."""
    if not stem:
        return False
    if any(symbol in stem for symbol in symbols):
        return True
    return len(stem) >= MIN_CONTAINED_STEM and any(stem in symbol for symbol in symbols)


def _census_key(relative: Path) -> str:
    """The directory a counted class belongs to; `.` for files directly under `tests/unit/`.

    Without this a top-level file keys on its own FILENAME — putting filenames in a table of
    directories, and giving every such file its own independently-ratcheting category.
    """
    return relative.parts[0] if len(relative.parts) > 1 else "."


def census(repo_root: Path = REPO_ROOT) -> dict[str, int]:
    """Count unit test classes that name no subject, keyed by top-level test directory.

    Per-directory rather than one total: a single number lets a fix in `graph` (1 class) pay for a
    regression in `assurance` (98).
    """
    symbols = source_symbols(repo_root)
    unit_root = repo_root / "tests" / "unit"
    counts: Counter[str] = Counter()
    for path in unit_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            parsed = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for node in ast.walk(parsed):
            if not isinstance(node, ast.ClassDef) or not node.name.startswith("Test"):
                continue
            if not class_names_subject(node.name[len("Test") :], symbols):
                counts[_census_key(path.relative_to(unit_root))] += 1
    return dict(counts)


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, int] | None:
    """The frozen counts, or None when the baseline has never been written."""
    if not path.is_file():
        return None
    return dict(json.loads(path.read_text(encoding="utf-8"))["counts"])


def write_baseline(counts: dict[str, int], path: Path = BASELINE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "_comment": (
                    "Frozen count of unit test classes that name no class or function under "
                    "test. Regenerate ONLY with `python scripts/check_conventions.py "
                    "--update-naming-baseline`, and expect the diff to be reviewed: every "
                    "increase is a test class whose name does not say what it tests."
                ),
                "counts": dict(sorted(counts.items())),
                "total": sum(counts.values()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def regressions(current: dict[str, int], baseline: dict[str, int]) -> list[tuple[str, int, int]]:
    """`(directory, baseline, current)` for every directory whose count grew.

    A directory absent from the baseline starts at zero, not at "unmeasured" — otherwise a new
    test package is a free pass.
    """
    return [
        (key, baseline.get(key, 0), value)
        for key, value in sorted(current.items())
        if value > baseline.get(key, 0)
    ]
