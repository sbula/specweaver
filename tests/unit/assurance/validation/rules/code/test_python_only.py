# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C01, C06 and C08 judge Python only, and say why they skip anything else.

Proves: TECH-093 FR-1
Proves: TECH-093 FR-2
Proves: TECH-093 NFR-1
Proves: TECH-093 NFR-2

| Bucket | Case |
|---|---|
| Happy | a `.py` file keeps today's PASS, FAIL and WARN |
| Boundary | `.pyi` is checked; `.kt`, `.java`, `.rs`, `.ts` skip naming the language, even text that parses as Python |
| Degradation | a `.py` file with a syntax error keeps C01 FAIL and the C06/C08 syntax SKIP |
| Hostile | no path, no ending or `.txt` skip as "language unknown", even text that would fail C01 |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c01_syntax_valid import SyntaxValidRule
from specweaver.assurance.validation.rules.code.c06_no_bare_except import NoBareExceptRule
from specweaver.assurance.validation.rules.code.c08_type_hints import TypeHintsRule

_RULES = [SyntaxValidRule, NoBareExceptRule, TypeHintsRule]

# Parses as Python, so before TECH-093 all three rules judged it.
_PARSES_AS_PYTHON = "x = 1\n"
# Would fail C01 if it were ever parsed as Python.
_BROKEN = "def foo(\n"


@pytest.mark.parametrize("rule_cls", _RULES)
@pytest.mark.parametrize(
    ("name", "text", "language"),
    [
        ("Cart.kt", "package shop\n\nclass Cart { fun total(): Int = 0 }\n", "kotlin"),
        ("build.gradle.kts", 'plugins { kotlin("jvm") }\n', "kotlin"),
        ("Main.java", "class Main {}\n", "java"),
        ("lib.rs", "fn main() {}\n", "rust"),
        ("app.ts", _PARSES_AS_PYTHON, "typescript"),
    ],
)
def test_another_language_is_skipped_naming_it(rule_cls, name, text, language) -> None:
    result = rule_cls().check(text, Path("src") / name)

    assert result.status == Status.SKIP
    assert result.message.startswith(f"{language}:")
    assert "Python only" in result.message


@pytest.mark.parametrize("rule_cls", _RULES)
@pytest.mark.parametrize("path", [None, Path("bin/tool"), Path("notes.txt")])
def test_an_unknown_language_is_skipped_and_never_parsed(rule_cls, path) -> None:
    result = rule_cls().check(_BROKEN, path)

    assert result.status == Status.SKIP
    assert result.message.startswith("language unknown:")


@pytest.mark.parametrize("suffix", [".py", ".pyi"])
def test_python_keeps_its_verdicts(suffix: str) -> None:
    path = Path("m" + suffix)
    code = "def ok() -> int:\n    return 1\n\n\ndef bad():\n    try:\n        pass\n    except:\n        pass\n"

    assert SyntaxValidRule().check(code, path).status == Status.PASS
    assert NoBareExceptRule().check(code, path).status == Status.WARN
    assert TypeHintsRule().check(code, path).status == Status.WARN
    assert SyntaxValidRule().check("", path).status == Status.PASS


def test_a_python_syntax_error_keeps_today_s_results() -> None:
    path = Path("broken.py")

    c01 = SyntaxValidRule().check(_BROKEN, path)
    c06 = NoBareExceptRule().check(_BROKEN, path)
    c08 = TypeHintsRule().check(_BROKEN, path)

    assert c01.status == Status.FAIL
    assert c01.findings[0].line == 1
    assert (c06.status, c06.message) == (Status.SKIP, "Cannot parse file (syntax error)")
    assert (c08.status, c08.message) == (Status.SKIP, "Cannot parse file (syntax error)")
