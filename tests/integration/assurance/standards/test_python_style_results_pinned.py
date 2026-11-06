# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The Python style results, pinned before the analyzer changes parser.

Proves: TECH-079 FR-17

Each case scans real files through `StandardsScanner` and compares one category with values worked
out by hand from the fixture text, never read back from the analyzer. Files are written at test
time, so every recency weight is 1.

| Bucket | Case |
|---|---|
| Happy | naming over functions, methods, nested, async and decorated defs and classes; specific and bare excepts |
| Boundary | only plain parameters count for type hints; an empty or blank docstring is none; `except*`; `from __future__` |
| Degradation | a file with a syntax error is skipped; a file with bytes that are not UTF-8 is still read |
| Hostile | an f-string or a bytes string is no docstring; a test file importing two frameworks takes the shallower one |
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.standards.scanner import StandardsScanner

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _category(tmp_path: Path, files: dict[str, str | bytes], category: str) -> tuple:
    paths = []
    for name, text in files.items():
        path = tmp_path / name
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(textwrap.dedent(text), encoding="utf-8")
        paths.append(path)
    found = [r for r in StandardsScanner().scan(paths) if r.category == category]
    assert len(found) == 1
    (result,) = found
    assert result.language == "python"
    return dict(result.dominant), result.confidence, result.sample_size


def test_naming(tmp_path: Path) -> None:
    files = {
        "names.py": """
            def top_snake(): pass
            def topCamel(): pass
            async def fetch_it(): pass
            @deco
            def decorated_one(): pass
            def _private(): pass
            f = lambda: 0
            class Outer:
                def method_one(self):
                    def inner_fn(): pass
            class Second: pass
            class lower_class: pass
        """,
    }

    dominant, confidence, sample = _category(tmp_path, files, "naming")

    # functions: 5 snake_case, 1 camelCase (`_private` skipped); classes: 2 PascalCase, 1 snake_case
    assert dominant == {"function_style": "snake_case", "class_style": "PascalCase"}
    assert confidence == pytest.approx(5 / 6)
    assert sample == 9


def test_error_handling(tmp_path: Path) -> None:
    files = {
        "errors.py": """
            try: pass
            except: pass
            try: pass
            except ValueError: pass
            except (KeyError, TypeError): pass
            try: pass
            except* OSError: pass
            try: pass
            except KeyError, TypeError: pass
        """,
    }

    dominant, confidence, sample = _category(tmp_path, files, "error_handling")

    assert dominant == {"exception_style": "specific"}
    assert confidence == pytest.approx(4 / 5)
    assert sample == 5


def test_only_plain_parameters_count_for_type_hints(tmp_path: Path) -> None:
    files = {
        "hints.py": """
            def a(x: int): pass
            def b(x) -> int: pass
            def p(x: int, /): pass
            def k(*, x: int): pass
            def v(*args: int): pass
            def kw(**kw: int): pass
            def plain(x): pass
            class C:
                def m(self, x: int): pass
        """,
    }

    dominant, confidence, sample = _category(tmp_path, files, "type_hints")

    # yes: a, b, m; no: p (positional-only), k (keyword-only), v, kw, plain
    assert dominant == {"usage": "no"}
    assert confidence == pytest.approx(5 / 8)
    assert sample == 8


def test_docstrings(tmp_path: Path) -> None:
    files = {
        "docs.py": '''
            def d1():
                """Plain."""
            def d2():
                "a" "b"
            def d3():
                f"doc {d1}"
            def d4():
                b"bytes"
            def d5():
                """"""
            def d6():
                x = 1
                """late"""
            def d7():
                """   """
            async def d8():
                """Async doc."""
        ''',
    }

    dominant, confidence, sample = _category(tmp_path, files, "docstrings")

    # documented: d1, d2 (one string once joined), d8 — 3 of 8 is "low"
    assert dominant == {"coverage": "low"}
    assert confidence == pytest.approx(3 / 8)
    assert sample == 8


def test_import_patterns(tmp_path: Path) -> None:
    files = {
        "imports.py": """
            from __future__ import annotations
            import os
            import sys
            from x.y import z
            from . import a
            from ..b import c
            from .c import d
        """,
    }

    dominant, confidence, sample = _category(tmp_path, files, "import_patterns")

    assert dominant == {"style": "absolute"}
    assert confidence == pytest.approx(4 / 7)
    assert sample == 7


def test_test_patterns_take_the_shallower_import(tmp_path: Path) -> None:
    files = {
        # the nested `import pytest` comes first in the text; the top-level `unittest` is shallower
        "test_both.py": "def helper():\n    import pytest\nimport unittest\n",
        "x_test.py": "import pytest\n",
        "test_unit.py": "import unittest\n",
        "plain.py": "import pytest\n",
    }

    dominant, confidence, sample = _category(tmp_path, files, "test_patterns")

    assert dominant == {"framework": "unittest"}
    assert confidence == pytest.approx(2 / 3)
    assert sample == 3


def test_a_broken_file_is_skipped_and_bad_bytes_are_read(tmp_path: Path) -> None:
    files = {
        "good.py": "def good_name(): pass\n",
        "broken.py": "def Broken_Name():\n    pass\ndef (\n",
        "bytes.py": b"def bytes_name():\n    s = '\xff'\n",
    }

    dominant, confidence, sample = _category(tmp_path, files, "naming")

    assert dominant == {"function_style": "snake_case"}
    assert confidence == pytest.approx(1.0)
    assert sample == 2
