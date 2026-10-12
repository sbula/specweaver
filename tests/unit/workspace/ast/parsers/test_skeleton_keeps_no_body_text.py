# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A skeleton shows signatures and docstrings, and nothing of a body — in braced and indented code.

Proves: D-SENS-02 FR-1

| Bucket | Case |
|---|---|
| Happy | a Python function's body becomes `...`; its docstring stays |
| Boundary | a Java body keeps its braces around `...` |
| Degradation | a file with a syntax error still gives a skeleton (NFR-2) |
| Hostile | not applicable — the input is the user's own code |
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure

_PY = '''def area(r: float) -> float:
    return 3.14 * r * r


def add(a: int, b: int) -> int:
    """Sum."""
    return a + b
'''


def test_a_python_body_leaves_no_letter_behind() -> None:
    skeleton = PythonCodeStructure().extract_skeleton(_PY)

    assert skeleton == (
        "def area(r: float) -> float:\n     ... \n\n\ndef add(a: int, b: int) -> int:\n"
        '    """Sum.""" ... \n'
    )


def test_a_java_body_keeps_its_braces() -> None:
    skeleton = JavaCodeStructure().extract_skeleton(
        'class A {\n    String hi() { return "hi"; }\n}\n'
    )

    assert "String hi() { ... }" in skeleton
    assert "return" not in skeleton


def test_a_syntax_error_still_gives_a_skeleton() -> None:
    skeleton = PythonCodeStructure().extract_skeleton(
        "def ok() -> int:\n    return 1\n\ndef bad(:\n    pass\n"
    )

    assert "def ok() -> int:" in skeleton
    assert "return 1" not in skeleton
