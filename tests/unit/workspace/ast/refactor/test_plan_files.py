# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A file created only where nothing is, and deleted only when nothing uses it.

Proves: D-SENS-06 FR-12
Proves: D-SENS-06 FR-13

| Bucket | Case |
|---|---|
| Happy | a new Python file; an unused file deleted |
| Boundary | a new SQL or Markdown file; a Go file whose function is used in its package |
| Degradation | code with a syntax error; a file used only through an unsure spot |
| Hostile | an existing, protected or outside path; a delete of an imported file, a header, a Rust module |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.ast.refactor.files import FilePlan, plan_create, plan_delete
from specweaver.workspace.ast.refactor.rename import RenameRefusal, Spot

_PY = PythonCodeStructure()

_FILES = {
    "app/__init__.py": "",
    "app/util.py": "def shout(n):\n    return n\n",
    "app/main.py": "from app.util import shout\n\nprint(shout('a'))\n",
    "app/lonely.py": "def alone():\n    return 1\n",
}


# --- create ----------------------------------------------------------------------------------


def test_a_new_python_file() -> None:
    plan = plan_create(_FILES, "app/new.py", "def fresh():\n    return 2\n", _PY)
    assert isinstance(plan, FilePlan)
    assert plan.changes == {"app/new.py": "def fresh():\n    return 2\n"}
    assert plan.delete is None


@pytest.mark.parametrize("path", ["db/new.sql", "docs/new.md"])
def test_a_new_file_in_any_language_with_a_parser(path: str) -> None:
    code = "CREATE TABLE t (id INT);\n" if path.endswith(".sql") else "# Title\n"
    assert isinstance(plan_create(_FILES, path, code, _PY), FilePlan)


def test_code_that_does_not_parse_refuses() -> None:
    assert "parse" in plan_create(_FILES, "app/bad.py", "def f(:\n", _PY).reason  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("app/util.py", "exists"),
        ("../x.py", "outside"),
        ("/etc/x.py", "outside"),
        (".env/x.py", "protected"),
        ("app/context.yaml", "protected"),
        ("app/x.unknown", "no parser"),
    ],
)
def test_a_path_that_cannot_be_created(path: str, reason: str) -> None:
    refusal = plan_create(_FILES, path, "x = 1\n", _PY)
    assert isinstance(refusal, RenameRefusal)
    assert reason in refusal.reason


# --- delete ----------------------------------------------------------------------------------


def test_an_unused_file_is_deleted() -> None:
    plan = plan_delete(_FILES, "app/lonely.py", _PY)
    assert isinstance(plan, FilePlan)
    assert (plan.changes, plan.delete) == ({}, "app/lonely.py")


def test_an_imported_file_refuses_and_names_the_importer() -> None:
    refusal = plan_delete(_FILES, "app/util.py", _PY)
    assert isinstance(refusal, RenameRefusal)
    assert Spot("app/main.py", 1) in refusal.spots


def test_an_unsure_use_refuses() -> None:
    files = {
        **_FILES,
        "app/dyn.py": "import importlib\nm = importlib.import_module('app.lonely')\n",
    }
    refusal = plan_delete(files, "app/lonely.py", _PY)
    assert isinstance(refusal, RenameRefusal)
    assert refusal.spots == [Spot("app/dyn.py", 2)]


def test_a_go_function_used_in_its_package_refuses() -> None:
    files = {
        "go.mod": "module m\n",
        "a/a.go": "package a\n\nfunc F() {}\n",
        "a/b.go": "package a\n\nfunc G() { F() }\n",
    }
    refusal = plan_delete(files, "a/a.go", GoCodeStructure())
    assert isinstance(refusal, RenameRefusal)
    assert refusal.spots == [Spot("a/b.go", 3)]


def test_a_header_used_by_a_source_refuses() -> None:
    files = {
        "src/u.h": "int total(int a);\n",
        "src/u.c": '#include "u.h"\nint total(int a) { return a; }\n',
    }
    refusal = plan_delete(files, "src/u.h", CCodeStructure())
    assert isinstance(refusal, RenameRefusal)
    assert {s.path for s in refusal.spots} == {"src/u.c"}


def test_a_rust_module_is_always_used_by_its_mod_line() -> None:
    files = {
        "Cargo.toml": '[package]\nname = "a"\n',
        "src/lib.rs": "mod util;\n",
        "src/util.rs": "pub fn x() {}\n",
    }
    refusal = plan_delete(files, "src/util.rs", RustCodeStructure())
    assert isinstance(refusal, RenameRefusal)
    assert refusal.spots == [Spot("src/lib.rs", 1)]


def test_a_java_class_used_from_another_package_refuses() -> None:
    files = {
        "src/a/util/G.java": "package a.util;\n\npublic class G {}\n",
        "src/a/M.java": "package a;\n\nimport a.util.G;\n\nclass M { G g; }\n",
    }
    refusal = plan_delete(files, "src/a/util/G.java", JavaCodeStructure())
    assert isinstance(refusal, RenameRefusal)
    assert {s.path for s in refusal.spots} == {"src/a/M.java"}


def test_a_file_that_is_not_in_the_project_or_has_no_resolver_refuses() -> None:
    assert plan_delete(_FILES, "app/missing.py", _PY).reason  # type: ignore[union-attr]
    assert "not supported" in plan_delete({"d/x.sql": "SELECT 1;\n"}, "d/x.sql", _PY).reason  # type: ignore[union-attr]


def test_a_symbol_whose_users_cannot_be_told_refuses() -> None:
    files = {**_FILES, "app/twice.py": "def f():\n    return 1\n\ndef f():\n    return 2\n"}
    refusal = plan_delete(files, "app/twice.py", _PY)
    assert isinstance(refusal, RenameRefusal)
    assert refusal.spots == [Spot("app/twice.py", 1)]
