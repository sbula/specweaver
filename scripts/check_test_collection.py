#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A test file that contributes no test is invisible coverage. `TECH-051`.

A `test_*.py` from which pytest collects nothing still reads as coverage — in a directory listing,
in review, and to anyone deciding not to write a test because one appears to exist. That last one
is not hypothetical: `INT-US-16` was about to skip a test on the strength of
`tests/unit/core/flow/engine/test_runner_telemetry.py`, which holds six tests for the pipeline
runner's telemetry flush and **collected none of them**, because its class is named
`QARunnerTelemetryFlush` and pytest collects `Test*`.

Measured 2026-08-16 across 570 test files: 13 excluded only by the `live` marker (legitimate) and
**12 uncollectable at all** — 3 files hiding 24 tests behind an unprefixed class, and 9 empty stubs
named after `sandbox/protocol`, an `A-VAL-01` package at DAL-A with no real tests. All twelve are
closed; this exists so the thirteenth cannot arrive quietly.

## Why static, and what pays for it

A real `--collect-only` pass over this suite costs 15-20 seconds — affordable once at the `doc`
gate, too slow for `quick`, which is where a rule about test files is actually seen. So the rule is
applied statically over the AST and runs in well under a second.

The risk of approximating someone else's collection rules is bought back by
`compare_with_pytest()`, which `tests/unit/scripts/test_check_test_collection.py` runs against the
real collector and asserts agreement file by file. If the two ever diverge — a custom
`python_classes`, a plugin, a pytest upgrade — that test fails rather than this check being quietly
wrong.

## What is NOT excluded, and why there is no exemption list

`conftest.py`, `rendering.py` and `__init__.py` need no exemption: the walk globs `test_*.py`, so
they were never candidates. An early draft carried a `_NOT_A_TEST_MODULE` tuple for them and a test
that appeared to cover it — **a mutant emptying the tuple changed nothing**, which is how a dead
constant and its vacuous test were found together. Both are gone.

## Why the marker files are not holes

13 files carry `pytest.mark.live` and are excluded from the default run on purpose. They **collect**
fine; they are deselected. Counting them would put 13 permanent entries in the output and teach the
reader to skip it — which is precisely how the 24 hidden tests survived.

Usage:
    python scripts/check_test_collection.py           # judge the tree
    python scripts/check_test_collection.py --list    # every file and its test count
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: pytest's defaults. Read from `pyproject.toml` rather than hardcoded — a project that sets
#: `python_classes` would make every assumption here wrong, silently. `NFR-2`.
_DEFAULT_CLASS_PREFIX = "Test"
_DEFAULT_FUNCTION_PREFIX = "test"


def collection_prefixes(repo_root: Path) -> tuple[str, str]:
    """`(class prefix, function prefix)` pytest will use, read from `pyproject.toml`.

    Raises:
        NotImplementedError: the project configures a pattern this rule cannot honour. Failing
            loudly beats guessing: a wrong prefix turns every file into a false accusation.
    """
    config = repo_root / "pyproject.toml"
    if not config.is_file():
        return _DEFAULT_CLASS_PREFIX, _DEFAULT_FUNCTION_PREFIX

    ini = tomllib.loads(config.read_text(encoding="utf-8")).get("tool", {}).get("pytest", {})
    ini = ini.get("ini_options", ini)

    for key in ("python_classes", "python_functions"):
        value = ini.get(key)
        if value is None:
            continue
        patterns = value.split() if isinstance(value, str) else list(value)
        if len(patterns) != 1 or not patterns[0].endswith("*"):
            msg = (
                f"pyproject sets {key} = {value!r}, which this static rule cannot honour. "
                "Teach it the new pattern, or the check will report false findings."
            )
            raise NotImplementedError(msg)

    def _prefix(key: str, default: str) -> str:
        value = ini.get(key)
        return value.split()[0].rstrip("*") if isinstance(value, str) else default

    return _prefix("python_classes", _DEFAULT_CLASS_PREFIX), _prefix(
        "python_functions", _DEFAULT_FUNCTION_PREFIX
    )


def _count(body: list[ast.stmt], class_prefix: str, function_prefix: str) -> int:
    """Tests pytest would collect from these statements.

    Recurses into `Test*` classes, because pytest does: a nested test class is real coverage, and
    missing it would make this rule accuse a file that is fine.
    """
    found = 0
    for node in body:
        if isinstance(node, ast.ClassDef) and node.name.startswith(class_prefix):
            found += _count(node.body, class_prefix, function_prefix)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            function_prefix
        ):
            found += 1
    return found


def contributed_tests(path: Path, prefixes: tuple[str, str] | None = None) -> int:
    """How many tests pytest would collect from `path`.

    Raises:
        SyntaxError: the file does not parse. Reporting it as "contributes nothing" would send the
            reader looking for a missing class instead of a missing colon.
    """
    class_prefix, function_prefix = prefixes or collection_prefixes(REPO_ROOT)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return _count(tree.body, class_prefix, function_prefix)


def _reason(path: Path, class_prefix: str) -> str:
    """Why this file contributes nothing, in the words of its own contents."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hiding = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and not node.name.startswith(class_prefix)
        and any(
            isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test")
            for m in node.body
        )
    ]
    if hiding:
        names = ", ".join(hiding)
        return f"class {names} holds test methods but is not named {class_prefix}*"
    if not [
        n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]:
        return "the file defines nothing at all"
    return "no test function and no test class"


def offenders(tests_root: Path) -> list[tuple[str, str]]:
    """`(path relative to tests_root, reason)` for every file contributing no test."""
    class_prefix, function_prefix = collection_prefixes(REPO_ROOT)
    found: list[tuple[str, str]] = []
    for path in sorted(tests_root.rglob("test_*.py")):
        if contributed_tests(path, (class_prefix, function_prefix)) == 0:
            found.append((path.relative_to(tests_root).as_posix(), _reason(path, class_prefix)))
    return found


def compare_with_pytest(repo_root: Path) -> tuple[set[str], set[str]]:
    """`(files this rule says contribute, files pytest says contribute)`, for the whole repo.

    The marker filter is deliberately dropped: `-m 'not live'` DESELECTS, so leaving it in would
    make pytest disagree about 13 files that collect perfectly well.

    `--override-ini` is load-bearing too — this repo's `addopts` carries `-v`, which turns
    `--collect-only -q` into a tree rather than node ids. A first attempt at this census parsed the
    tree and concluded all 570 files were empty.
    """
    tests_root = repo_root / "tests"
    prefixes = collection_prefixes(repo_root)
    static = {
        p.relative_to(tests_root).as_posix()
        for p in sorted(tests_root.rglob("test_*.py"))
        if contributed_tests(p, prefixes) > 0
    }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:tach",
            "--override-ini=addopts=--import-mode=importlib",
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    live = {
        line.split("::")[0][len("tests/") :]
        for line in result.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    }
    return static, live


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(REPO_ROOT), help="repository root to judge")
    ap.add_argument("--list", action="store_true", help="print every file and its test count")
    args = ap.parse_args(argv)

    tests_root = Path(args.root) / "tests"
    if not tests_root.is_dir():
        print(f"could not run: no tests directory under {args.root}", file=sys.stderr)
        return 2

    if args.list:
        prefixes = collection_prefixes(REPO_ROOT)
        for path in sorted(tests_root.rglob("test_*.py")):
            count = contributed_tests(path, prefixes)
            print(f"  {count:4}  {path.relative_to(tests_root).as_posix()}")
        return 0

    found = offenders(tests_root)
    if found:
        print(f"Test files that collect NOTHING ({len(found)}):\n")
        for path, reason in found:
            print(f"  tests/{path}\n        {reason}")
        print(
            "\nA file like this reads as coverage in a listing and in review, and is the reason a "
            "story skips a test it believes already exists. Fix the cause the reason names — rename "
            "the class, or write the tests the filename promises.\n"
            "**Deleting the file is almost never right**: nine such stubs turned out to be the only "
            "visible trace that `A-VAL-01`, a delivered DAL-A capability, had no tests at all."
        )
        return 1

    total = sum(1 for p in tests_root.rglob("test_*.py"))
    print(f"Test collection: all {total} test file(s) contribute at least one test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
