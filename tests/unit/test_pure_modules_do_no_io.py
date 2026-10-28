# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A `pure-logic` module reads no files and runs no processes.

Proves: TECH-081 FR-9

tach sees imports, not I/O, so this test is the only check of the label. It matches direct calls
and imports; an aliased call passes, and review covers that.

| Bucket | Case |
|---|---|
| Happy | every listed module makes no file or process call |
| Boundary | a name like `opened`, or `open(` inside a string, is not a call |
| Degradation | a listed module that does not exist fails instead of passing on nothing |
| Hostile | `import subprocess as sp` and `from os import path` are still found |
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "specweaver"
#: Modules labelled `pure-logic` whose code this test reads.
_PURE = ("commons",)
_IO_METHODS = frozenset(
    {
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "is_file",
        "is_dir",
        "exists",
        "iterdir",
        "glob",
        "rglob",
    }
)
_IO_MODULES = frozenset({"os", "subprocess", "shutil"})


def _io_calls(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open":
                found.append("open")
            elif isinstance(func, ast.Attribute) and func.attr in _IO_METHODS:
                found.append(func.attr)
        elif isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.split(".")[0] in _IO_MODULES]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in _IO_MODULES:
            found.append(str(node.module))
    return found


def test_pure_modules_do_no_io() -> None:
    offenders = {
        str(f.relative_to(_SRC)): calls
        for module in _PURE
        for f in sorted((_SRC / module).rglob("*.py"))
        if (calls := _io_calls(f.read_text(encoding="utf-8")))
    }

    assert offenders == {}


def test_every_listed_module_exists() -> None:
    assert [m for m in _PURE if not list((_SRC / m).rglob("*.py"))] == []


def test_a_lookalike_name_or_string_is_not_io() -> None:
    assert _io_calls('opened = 1\nmsg = "open(x).read_text()"\n') == []


def test_direct_calls_are_found() -> None:
    assert _io_calls("open('f')\np.read_text()\np.exists()\n") == ["open", "read_text", "exists"]


def test_aliased_and_from_imports_are_found() -> None:
    assert _io_calls("import subprocess as sp\nfrom os import path\n") == ["subprocess", "os"]
