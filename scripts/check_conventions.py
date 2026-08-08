#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Coding conventions: file headers, banned grab-bag names, and templated-family conformance.

Most gates judge a file on its own. This one judges a file against its SIBLINGS, which is the
only way to catch the failure mode where an agent adds the eleventh member of a family and
quietly omits what the other ten all do. Nothing else in the battery can see that: the new file
lints clean, types clean, and is under every threshold -- it is simply not the same shape as its
family, and the divergence is invisible until something calls the method that is not there.

Five rules:

  R1 GRAB-BAG NAMES  Module and package names matching util(s)/helper(s)/misc/shared/common are
                     rejected outside the L0 `commons` leaf. Named as a required guardrail by
                     TECH-008: such a module has no contract, so it accretes anything, and the
                     accretion is what the dependency graph then has to route around. Zero
                     violations today -- this rule exists to keep it that way.

  R2 FILE HEADER     Every source file carries the copyright and licence lines.

  R3 FAMILY SHAPE    A declared family's members must inherit the family base and carry the
                     family's class-name suffix. Where the naming genuinely derives from the
                     directory it is checked too -- but only where it genuinely does. The ten
                     tree-sitter parsers derive theirs; the sandbox atoms do NOT
                     (`execution/core/atom.py` defines `BashActionAtom`), so asserting a single
                     universal convention would manufacture a false positive and teach everyone
                     to ignore the rule.

  R4 FAMILY MEMBERS  A member missing a public method that EVERY other member defines is
                     reported, along with the siblings that have it. The bar is deliberately
                     "every other member", not a majority: a conservative rule that fires rarely
                     gets fixed, and a chatty one gets suppressed.

  R5 TEST NAMING     A test's file, class and function names carry no registry ID. The ticket that
                     paid for a test is an accident of timing; the behaviour outlives it, and the
                     name is what the next reader searches for. Covers every tier -- the first
                     version inspected `tests/e2e/` filenames only, and three offenders survived it
                     purely by living elsewhere. Names only: the one sanctioned `Proves:` docstring
                     tag is what `check_fr_coverage.py` reads, and flagging it would set the two
                     gates against each other.

Exit 1 on any violation.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Names with no contract of their own — they accrete whatever has no better home.
GRAB_BAG_NAMES = {"util", "utils", "helper", "helpers", "misc", "shared", "common"}
#: The one sanctioned exception: the L0 leaf package that is explicitly the shared kernel.
#: `tests/fixtures/` is exempt for a different reason — it holds sample projects standing in for
#: OTHER people's code. A fixture named `utils.py` is representative input, and "fixing" it would
#: destroy the very shape the fixture exists to reproduce.
GRAB_BAG_EXEMPT_PATHS = {"src/specweaver/commons", "tests/fixtures"}

HEADER_MARKERS = ("Copyright (c)", "Licensed under the Apache License")
HEADER_SCAN_LINES = 5

#: Registry IDs that must not appear in a test's file, class or function name (R5).
#:
#: Each alternative is anchored on something a registry ID has and ordinary prose does not: the
#: `int_us_` prefix, a topic word between separators, the `tech_` prefix, a `sf<n>` sub-feature tag.
#: What it must NOT match is validation rule IDs — `c01`..`c13`, `s07`, `s12` — which name
#: `test_c05_architecture_integration.py` and nine siblings. `c05` is a rule, part of the domain
#: vocabulary, and outlives every ticket that touched it. A looser `[a-z]\d{2}` pattern flags all
#: ten, and the reflex fix is a fresh allowlist — which is how the previous allowlist was born.
_STORY_ID_IN_NAME = re.compile(
    r"int_us_\d+|_(ui|sens|flow|intl|val|exec)_\d{2}_|tech_\d{3}|_sf_?\d", re.I
)
TESTS_ROOT = "tests"


@dataclass(frozen=True)
class Family:
    """A set of files that are meant to be the same shape."""

    name: str
    glob: str
    base: str
    suffix: str
    #: Index into the file's parent chain that supplies the class-name prefix; None to skip.
    prefix_from: int | None = None


FAMILIES = (
    Family(
        name="tree-sitter parser",
        glob="src/specweaver/workspace/ast/parsers/*/codestructure.py",
        base="BaseTreeSitterParser",
        suffix="CodeStructure",
        prefix_from=0,
    ),
    Family(
        name="sandbox atom",
        glob="src/specweaver/sandbox/*/core/atom.py",
        base="Atom",
        suffix="Atom",
    ),
)


@dataclass(frozen=True)
class Violation:
    rule: str
    path: Path
    message: str


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


# ---------------------------------------------------------------------------
# R1 / R2 — per-file rules
# ---------------------------------------------------------------------------


def check_grab_bag_name(path: Path) -> list[Violation]:
    rel = _rel(path)
    if any(rel.startswith(exempt) for exempt in GRAB_BAG_EXEMPT_PATHS):
        return []

    parts = [*Path(rel).parts[:-1], Path(rel).stem]
    offending = [p for p in parts if p.lower() in GRAB_BAG_NAMES]
    return [
        Violation(
            "R1",
            path,
            f"'{name}' names a dumping ground, not a contract — name it for what it "
            f"guarantees, or it will accrete whatever has no better home (TECH-008)",
        )
        for name in offending
    ]


def _snake(name: str) -> str:
    """`TestIntUs21Decomposition` -> `test_int_us_21_decomposition`.

    Class names are CamelCase, so the underscore-anchored pattern cannot see a registry ID in one
    without this. Splitting before an upper-case run and before a digit run is enough: the ID's own
    separators are what the pattern keys on.
    """
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", "_", name)
    return spaced.lower()


def _test_symbol_names(path: Path) -> list[str]:
    """Test class and function names defined in the file, or none if it will not parse.

    A syntax error is somebody else's failure, not a naming defect — degrade quietly, as
    `_family_class` does.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and (node.name.startswith("test") or node.name.startswith("Test"))
    ]


def check_registry_ids_in_names(path: Path, repo_root: Path = REPO_ROOT) -> list[Violation]:
    """R5: a test is named for what it exercises, never for the story that produced it.

    A story ID is an accident of when the work happened. The behaviour the test proves outlives
    it — and the name is what the next reader searches for. `test_feature_decomposition_e2e.py`
    tells you which ticket paid for the test; `test_feature_decomposition_e2e.py` tells you what
    breaks if it goes red.

    It also makes the tests navigable by subject, which is what lets a diff touching `workflows/`
    select the files that cover it instead of running all 191.

    Covers **every tier and every name** — file, class and function. The first version of this rule
    inspected `tests/e2e/` filenames only, and the three offenders that survived it did so purely by
    living elsewhere: two integration files and one unit file, plus two `_sf4` function names.

    **Names only.** Docstrings and comments are never inspected: a single trailing
    `Proves: TECH-NNN FR-N` tag is the one sanctioned place a registry ID may appear in a test, and
    `check_fr_coverage.py` reads it. Flagging it here would put the two gates in direct
    contradiction and make the citation convention impossible to satisfy.
    """
    rel = path.relative_to(repo_root).as_posix() if path.is_relative_to(repo_root) else _rel(path)
    if not rel.startswith(f"{TESTS_ROOT}/"):
        return []

    offenders = [path.name, *_test_symbol_names(path)]
    violations = []
    for name in offenders:
        match = _STORY_ID_IN_NAME.search(_snake(name))
        if match is not None:
            kind = "filename" if name == path.name else "test name"
            violations.append(
                Violation(
                    "R5",
                    path,
                    f"{kind} '{name}' carries the registry ID "
                    f"'{match.group(0).strip('_')}' — name it for the function, feature or "
                    "workflow under test instead",
                )
            )
    return violations


#: Every tree carrying first-party code. `tests/` joined once its 349 missing headers were
#: actually added (2026-07-29) rather than the rule being quietly narrowed to fit.
#:
#: Insertion order matters and is not obvious: the header goes AFTER a shebang and after any
#: file-level `# mypy:` / `# ruff:` pragma, because those are only honoured at the very top of a
#: file. Putting the copyright first would have silently re-enabled mypy on ~300 test files.
HEADER_TREES = ("src/", "scripts/", "tests/")


def missing_header_markers(path: Path) -> list[str]:
    """Which required header lines are absent. Detection only — says nothing about applicability."""
    try:
        head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:HEADER_SCAN_LINES])
    except (OSError, UnicodeDecodeError):
        return []
    return [m for m in HEADER_MARKERS if m not in head]


def check_header(path: Path) -> list[Violation]:
    if not _rel(path).startswith(HEADER_TREES):
        return []
    missing = missing_header_markers(path)
    if not missing:
        return []
    return [Violation("R2", path, f"missing header line(s): {', '.join(missing)}")]


# ---------------------------------------------------------------------------
# R3 / R4 — family rules
# ---------------------------------------------------------------------------


def _public_methods(node: ast.ClassDef) -> set[str]:
    return {
        s.name
        for s in node.body
        if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef) and not s.name.startswith("_")
    }


def _family_class(path: Path, family: Family) -> ast.ClassDef | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and family.base in _base_names(node):
            return node
    return None


def check_family(family: Family, repo_root: Path = REPO_ROOT) -> list[Violation]:
    members = sorted(repo_root.glob(family.glob))
    if len(members) < 2:
        return []

    violations: list[Violation] = []
    shapes: dict[Path, set[str]] = {}

    for path in members:
        node = _family_class(path, family)
        if node is None:
            violations.append(
                Violation(
                    "R3",
                    path,
                    f"{family.name}: defines no class inheriting '{family.base}'",
                )
            )
            continue

        if not node.name.endswith(family.suffix):
            violations.append(
                Violation(
                    "R3",
                    path,
                    f"{family.name}: class '{node.name}' does not end with '{family.suffix}'",
                )
            )

        if family.prefix_from is not None:
            owner = path.parents[family.prefix_from].name
            expected = f"{owner}{family.suffix}".replace("_", "").lower()
            if node.name.replace("_", "").lower() != expected:
                violations.append(
                    Violation(
                        "R3",
                        path,
                        f"{family.name}: class '{node.name}' does not match the name derived "
                        f"from '{owner}/' (expected something spelling '{owner}{family.suffix}')",
                    )
                )

        shapes[path] = _public_methods(node)

    # R4: a method every OTHER member defines is part of the family's contract.
    for path, methods in shapes.items():
        others = [m for p, m in shapes.items() if p != path]
        if not others:
            continue
        universal = set.intersection(*others) if others else set()
        for missing in sorted(universal - methods):
            violations.append(
                Violation(
                    "R4",
                    path,
                    f"{family.name}: missing '{missing}', which all {len(others)} sibling(s) "
                    f"define",
                )
            )

    return violations


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def iter_python_files(paths: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for path in paths:
        if path.is_dir():
            found.update(p for p in path.rglob("*.py") if "__pycache__" not in p.parts)
        elif path.suffix == ".py" and path.is_file():
            found.add(path)
    return sorted(found)


RULE_TITLES = {
    "R1": "Grab-bag module names",
    "R2": "Missing file header",
    "R3": "Family shape",
    "R4": "Family contract",
    "R5": "test named for a registry ID, not its subject",
}


def _print_violations(violations: list[Violation]) -> None:
    by_rule: dict[str, list[Violation]] = {}
    for v in violations:
        by_rule.setdefault(v.rule, []).append(v)

    for rule in sorted(by_rule):
        items = by_rule[rule]
        print(f"\n{rule} -- {RULE_TITLES[rule]} ({len(items)}):\n")
        for v in items:
            print(f"  {_rel(v.path)}\n      {v.message}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", help="files or directories (default: src, tests)")
    args = ap.parse_args(argv)

    raw = [Path(p) for p in args.paths] if args.paths else [REPO_ROOT / "src", REPO_ROOT / "tests"]
    missing = [p for p in raw if not p.exists()]
    if missing:
        for path in missing:
            print(f"FAIL  path not found: {path}")
        return 1

    files = iter_python_files(raw)
    violations: list[Violation] = []
    for path in files:
        violations.extend(check_grab_bag_name(path))
        violations.extend(check_header(path))
        violations.extend(check_registry_ids_in_names(path))

    # Families are checked whole: conformance is a statement about siblings, so a diff-scoped run
    # still compares the changed member against every other member of its family.
    scanned = {p.resolve() for p in files}
    for family in FAMILIES:
        for violation in check_family(family):
            if violation.path.resolve() in scanned or not args.paths:
                violations.append(violation)

    if not violations:
        print(f"Conventions: {len(files)} file(s) checked, {len(FAMILIES)} family(ies), all clean")
        return 0

    _print_violations(violations)
    print(f"\nBLOCKED: {len(violations)} convention violation(s) across {len(files)} file(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
