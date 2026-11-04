# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No flow handler calls a model itself, and none hides its complexity behind a `noqa`.

Proves: TECH-082 FR-6

Only workflows talk to the model; a handler gathers inputs, calls one, and writes the result back.
The engine's agentic `work_unit.py` loop is outside `core/flow/handlers` and is not scanned.

| Bucket | Case |
|---|---|
| Happy | every handler module is clean; a clean file passes |
| Boundary | a call inside a nested function is found; `hasattr(adapter, "generate_with_tools")` is not a call |
| Degradation | a file that does not parse is named, not skipped |
| Hostile | `getattr(adapter, "generate")(...)` is found; a bare `# noqa` on a `def` line hides C901 too; `self._generate(...)` is another name |
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_HANDLERS = (
    Path(__file__).resolve().parents[5] / "src" / "specweaver" / "core" / "flow" / "handlers"
)
_MODEL_CALLS = {"generate", "generate_with_tools"}
_HIDDEN = re.compile(r"#\s*noqa(?!\s*:)|#\s*noqa:[^\n]*\bC901\b")


def _called_name(func: ast.expr) -> str | None:
    """The method a call names: `x.generate(...)` or `getattr(x, "generate")(...)`."""
    if isinstance(func, ast.Attribute):
        return func.attr
    if (
        isinstance(func, ast.Call)
        and isinstance(func.func, ast.Name)
        and func.func.id == "getattr"
        and len(func.args) >= 2
        and isinstance(func.args[1], ast.Constant)
    ):
        return str(func.args[1].value)
    return None


def _offences(path: Path) -> list[str]:
    """Each model call and each hidden complexity warning in `path`, as `file:line`."""
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:  # expected: named, so an unreadable file cannot pass as clean
        return [f"{path}:unparsable"]
    found = [
        f"{path}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _called_name(node.func) in _MODEL_CALLS
    ]
    lines = text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            header = lines[node.lineno - 1]
            if _HIDDEN.search(header):
                found.append(f"{path}:{node.lineno}")
    return found


def test_no_handler_calls_a_model_or_hides_complexity() -> None:
    files = sorted(_HANDLERS.glob("*.py"))

    assert files
    assert [hit for f in files for hit in _offences(f)] == []


def test_a_clean_file_passes(tmp_path: Path) -> None:
    f = tmp_path / "clean.py"
    f.write_text("async def run(adapter):\n    return await adapter.review()\n", encoding="utf-8")

    assert _offences(f) == []


def test_a_nested_call_is_found(tmp_path: Path) -> None:
    f = tmp_path / "nested.py"
    f.write_text(
        "def outer(a):\n    async def inner():\n        return await a.generate([], None)\n",
        encoding="utf-8",
    )

    assert _offences(f) == [f"{f}:3"]


def test_a_hasattr_check_is_not_a_call(tmp_path: Path) -> None:
    f = tmp_path / "probe.py"
    f.write_text("def ok(a):\n    return hasattr(a, 'generate_with_tools')\n", encoding="utf-8")

    assert _offences(f) == []


def test_an_unparsable_file_is_named(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def (:\n", encoding="utf-8")

    assert _offences(f) == [f"{f}:unparsable"]


def test_a_getattr_call_is_found(tmp_path: Path) -> None:
    f = tmp_path / "sneaky.py"
    f.write_text(
        "async def run(a):\n    return await getattr(a, 'generate')([], None)\n", encoding="utf-8"
    )

    assert _offences(f) == [f"{f}:2"]


def test_a_noqa_on_a_def_line_is_found(tmp_path: Path) -> None:
    f = tmp_path / "hidden.py"
    f.write_text(
        "def a():  # noqa: C901\n    pass\n\n\ndef b():  # noqa\n    pass\n\n\n"
        "def c():  # noqa: E501\n    pass\n",
        encoding="utf-8",
    )

    assert _offences(f) == [f"{f}:1", f"{f}:5"]


def test_another_method_name_passes(tmp_path: Path) -> None:
    f = tmp_path / "other.py"
    f.write_text("async def run(self):\n    return await self._generate(1)\n", encoding="utf-8")

    assert _offences(f) == []
