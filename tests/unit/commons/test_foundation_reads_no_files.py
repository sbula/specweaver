# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`commons` does no file I/O, so every module may import it.

Proves: TECH-079 NFR-2

| Bucket | Case |
|---|---|
| Happy | no `commons` module calls a file-reading function |
| Boundary | the scan finds the `commons` modules, the profile decision among them |
| Degradation | — (a fixed source tree) |
| Hostile | a planted `Path(...).read_text()` or bare `open(...)` is caught |
"""

from __future__ import annotations

import ast
from pathlib import Path

import specweaver.commons.languages as languages

_FILE_CALLS = frozenset(
    {
        "open",
        "read_text",
        "read_bytes",
        "iterdir",
        "exists",
        "is_file",
        "is_dir",
        "glob",
        "listdir",
        "walk",
    }
)
_ROOT = Path(languages.__file__).parent


def _file_calls(source: str) -> list[str]:
    calls = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name in _FILE_CALLS:
            calls.append(f"{name}:{node.lineno}")
    return calls


def test_the_scan_finds_the_commons_modules() -> None:
    names = {path.name for path in _ROOT.rglob("*.py")}

    assert {"languages.py", "project_profile.py"} <= names


def test_a_planted_file_call_is_caught() -> None:
    assert _file_calls("from pathlib import Path\nPath('x').read_text()\n") == ["read_text:2"]
    assert _file_calls("with open('x') as f:\n    pass\n") == ["open:1"]


def test_no_commons_module_reads_files() -> None:
    found = {
        str(path.relative_to(_ROOT)): calls
        for path in sorted(_ROOT.rglob("*.py"))
        if (calls := _file_calls(path.read_text(encoding="utf-8")))
    }

    assert found == {}
