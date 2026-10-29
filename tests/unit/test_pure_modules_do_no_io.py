# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A `pure-logic` or `contract` module reads no files and runs no processes.

Proves: TECH-081 FR-9, FR-18, FR-19, FR-5

tach sees imports, not I/O, so this test is the only check of the label. It matches direct calls
and imports; an aliased call passes, and review covers that. A sub-folder whose own `context.yaml`
names another archetype (`io/`, `interfaces/`) is another module and is not read. A file the ledger
names may do I/O; it must still do some, or its allowance is stale.

| Bucket | Case |
|---|---|
| Happy | every listed module makes no file or process call |
| Boundary | a name like `opened`, or `open(` inside a string, is not a call |
| Degradation | a listed module that does not exist fails instead of passing on nothing |
| Hostile | `import subprocess as sp` and `from os import path` are still found |
| Boundary | an allowed file with no I/O left fails as stale; an allowed file needs a ledger row |
| Hostile | a pure sub-folder (`rules/`) is read; an `adapter` sub-folder (`io/`) is not |
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src" / "specweaver"
_LEDGER = _ROOT / "docs" / "architecture" / "06_lessons_and_future" / "known_boundary_violations.md"
#: Modules labelled `pure-logic` or `contract` whose code this test reads.
_PURE = ("commons", "assurance/validation", "workspace/context")
_PURE_ARCHETYPES = frozenset({"pure-logic", "contract"})
#: Files that may do I/O while the ledger names them.
_ALLOWED = (
    "assurance/validation/project_root.py",
    "assurance/validation/rules/code/c09_traceability.py",
    "assurance/validation/rules/spec/s04_dependency_dir.py",
)
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


def _archetype(folder: Path) -> str | None:
    """The archetype of the nearest `context.yaml` at or above `folder`."""
    for d in (folder, *folder.parents):
        manifest = d / "context.yaml"
        if manifest.is_file():
            return yaml.safe_load(manifest.read_text(encoding="utf-8")).get("archetype")
    return None


def _pure_files(module: str) -> list[Path]:
    return [
        f for f in sorted((_SRC / module).rglob("*.py")) if _archetype(f.parent) in _PURE_ARCHETYPES
    ]


def _calls(rel: str) -> list[str]:
    return _io_calls((_SRC / rel).read_text(encoding="utf-8"))


def test_pure_modules_do_no_io() -> None:
    offenders = {
        rel: calls
        for module in _PURE
        for f in _pure_files(module)
        if (rel := str(f.relative_to(_SRC))) not in _ALLOWED and (calls := _calls(rel))
    }

    assert offenders == {}


def test_every_allowed_file_still_does_io() -> None:
    assert [rel for rel in _ALLOWED if not _calls(rel)] == []


def test_every_allowed_file_has_a_ledger_row() -> None:
    ledger = _LEDGER.read_text(encoding="utf-8")
    assert [rel for rel in _ALLOWED if f"src/specweaver/{rel}" not in ledger] == []


def test_a_pure_sub_folder_is_read_and_an_adapter_one_is_not() -> None:
    files = {str(f.relative_to(_SRC)) for f in _pure_files("assurance/validation")}
    assert "assurance/validation/rules/code/c09_traceability.py" in files
    assert not any(
        f.startswith(("assurance/validation/io/", "assurance/validation/interfaces/"))
        for f in files
    )


def test_every_listed_module_exists() -> None:
    assert [m for m in _PURE if not list((_SRC / m).rglob("*.py"))] == []


def test_a_lookalike_name_or_string_is_not_io() -> None:
    assert _io_calls('opened = 1\nmsg = "open(x).read_text()"\n') == []


def test_direct_calls_are_found() -> None:
    assert _io_calls("open('f')\np.read_text()\np.exists()\n") == ["open", "read_text", "exists"]


def test_aliased_and_from_imports_are_found() -> None:
    assert _io_calls("import subprocess as sp\nfrom os import path\n") == ["subprocess", "os"]
