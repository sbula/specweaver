# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One table says which language a file ending is, and how that language names its tests.

Proves: TECH-078 FR-6, TECH-078 FR-3

| Bucket | Case |
|---|---|
| Happy | each language's endings name it; each language's test file name and folder from a code file |
| Boundary | an upper-case ending; `.pyi`, `.mjs`, `.cjs` (decision 1); no two languages share an ending |
| Degradation | an unknown ending, no ending, or a language without a test convention gives None |
| Hostile | a folder that looks like an ending (`a.py/b`) does not decide the language |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.commons.languages import (
    LANGUAGE_SUFFIXES,
    language_of,
    name_tests_for,
    root_of_tests,
)


@pytest.mark.parametrize(
    ("path", "language"),
    [
        ("src/orders.py", "python"),
        ("stubs/orders.pyi", "python"),
        ("Orders.java", "java"),
        ("Orders.kt", "kotlin"),
        ("build.gradle.kts", "kotlin"),
        ("src/orders.ts", "typescript"),
        ("src/App.tsx", "typescript"),
        ("lib/a.mjs", "javascript"),
        ("lib/a.cjs", "javascript"),
        ("src/lib.rs", "rust"),
        ("main.go", "go"),
        ("a.h", "c"),
        ("a.cxx", "cpp"),
        ("SRC/ORDERS.PY", "python"),
    ],
)
def test_an_ending_names_its_language(path: str, language: str) -> None:
    assert language_of(path) == language
    assert language_of(Path(path)) == language


@pytest.mark.parametrize("path", ["README.md", "notes", "", "data.sql", "a.py/b"])
def test_no_language_is_none(path: str) -> None:
    assert language_of(path) is None


def test_no_two_languages_share_an_ending() -> None:
    endings = [e for suffixes in LANGUAGE_SUFFIXES.values() for e in suffixes]

    assert len(endings) == len(set(endings))
    assert all(e == e.lower() and e.startswith(".") for e in endings)


@pytest.mark.parametrize(
    ("code", "language", "name", "root"),
    [
        ("orders.py", "python", "test_orders.py", "tests"),
        ("Orders.java", "java", "OrdersTest.java", "src/test/java"),
        ("Orders.kt", "kotlin", "OrdersTest.kt", "src/test/kotlin"),
        ("orders.ts", "typescript", "orders.test.ts", "tests"),
        ("orders.rs", "rust", "orders.rs", "tests"),
        ("orders.js", "javascript", "orders.test.js", "tests"),
    ],
)
def test_each_language_names_its_tests(code: str, language: str, name: str, root: str) -> None:
    assert name_tests_for(code, language) == name
    assert root_of_tests(language) == root


def test_a_language_without_a_convention_is_none() -> None:
    assert name_tests_for("main.go", "go") is None
    assert root_of_tests("go") is None
