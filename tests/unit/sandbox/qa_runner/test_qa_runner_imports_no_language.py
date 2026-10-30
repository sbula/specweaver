# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sandbox/qa_runner` imports nothing from `sandbox/language`, at any depth.

Proves: TECH-087 FR-12

`tach` sees one module, `specweaver.sandbox`, so it cannot hold this line; this test reads every
file with `ast` instead. The language runners import the QA contract, so the imports go one way.

| Bucket | Case |
|---|---|
| Happy | the real `sandbox/qa_runner` tree has no such import |
| Boundary | an import inside a function, under `TYPE_CHECKING`, and `from specweaver.sandbox import language` all count |
| Degradation | a file that does not parse fails the check, it is not skipped |
| Hostile | the dotted name in a docstring or a string is not an import |
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_QA_RUNNER = Path(__file__).resolve().parents[4] / "src" / "specweaver" / "sandbox" / "qa_runner"
_LANGUAGE = "specweaver.sandbox.language"


def _language_imports(source: str) -> list[str]:
    """Every import of `sandbox.language` in `source`, wherever it sits."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.startswith(_LANGUAGE)]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith(_LANGUAGE):
                found.append(node.module)
            else:
                names = (f"{node.module}.{a.name}" for a in node.names)
                found += [n for n in names if n.startswith(_LANGUAGE)]
    return found


def test_qa_runner_imports_nothing_from_language() -> None:
    files = sorted(_QA_RUNNER.rglob("*.py"))
    assert files, f"no source under {_QA_RUNNER}"

    offenders = {
        str(path.relative_to(_QA_RUNNER)): hits
        for path in files
        if (hits := _language_imports(path.read_text(encoding="utf-8")))
    }

    assert offenders == {}


@pytest.mark.parametrize(
    "source",
    [
        "def f():\n    from specweaver.sandbox.language.core.detect import detect_language\n",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import specweaver.sandbox.language.core\n",
        "from specweaver.sandbox import language\n",
    ],
    ids=["in-a-function", "type-checking", "from-the-parent"],
)
def test_every_form_of_the_import_counts(source: str) -> None:
    assert _language_imports(source)


def test_a_mention_in_a_string_is_not_an_import() -> None:
    source = '"""See specweaver.sandbox.language.core."""\nX = "specweaver.sandbox.language"\n'

    assert _language_imports(source) == []


def test_a_file_that_does_not_parse_fails() -> None:
    with pytest.raises(SyntaxError):
        _language_imports("def broken(:\n")
