# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An implementer renames code through its tool; no other role is offered the change intents.

Proves: D-SENS-06 FR-4
Proves: D-SENS-06 FR-6

Driven through `ToolDispatcher`, the path a model's tool call takes. The tool, the dispatcher's
grants, the executor and the parsers are real.

| Bucket | Case |
|---|---|
| Happy | `rename_symbol Greeter.greet → welcome`: both callers change, the README is reported |
| Boundary | a caller outside the write grants; a mention or a spot outside the read grants |
| Degradation | an unsure use refuses and changes nothing |
| Hostile | reviewer, planner, drafter cannot see or call it; `../`, protected files, an ungranted path |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
from specweaver.sandbox.code_structure.interfaces.tool import CodeStructureTool
from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.filesystem.core.executor import FileExecutor
from specweaver.sandbox.security import AccessMode, FolderGrant, WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

_GREETER = "class Greeter:\n    def greet(self, name):\n        return 'Hello ' + name\n"
_FILES = {
    "src/app/__init__.py": "",
    "src/app/greeter.py": _GREETER,
    "src/app/main.py": "from app.greeter import Greeter\n\nprint(Greeter.greet(Greeter(), 'x'))\n",
    "src/app/loud.py": (
        "from app.greeter import Greeter\n\nclass Loud(Greeter):\n"
        "    def shout(self, n):\n        return self.greet(n).upper()\n"
    ),
    "README.md": "Call greet to say hello.\n",
}
_RENAME = {"path": "src/app/greeter.py", "symbol_name": "Greeter.greet", "new_name": "welcome"}


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def _dispatcher(root: Path, role: str = "implementer") -> ToolDispatcher:
    return ToolDispatcher.create_standard_set(
        WorkspaceBoundary(roots=[root]), role=role, allowed_tools=["ast"]
    )


def _tool(root: Path, grants: list[FolderGrant]) -> CodeStructureTool:
    executor = FileExecutor(root)
    return CodeStructureTool(CodeStructureAtom(executor), "implementer", grants, executor=executor)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return _write(tmp_path / "project", _FILES)


# --- Happy -----------------------------------------------------------------------------------


async def test_the_implementer_renames_a_method_and_its_callers(project: Path) -> None:
    result = await _dispatcher(project).execute("rename_symbol", _RENAME)

    assert "error" not in result, result
    assert "def welcome(self, name)" in (project / "src/app/greeter.py").read_text()
    assert "Greeter.welcome(Greeter(), 'x')" in (project / "src/app/main.py").read_text()
    assert "self.welcome(n).upper()" in (project / "src/app/loud.py").read_text()
    assert result["changed"] == ["src/app/greeter.py", "src/app/loud.py", "src/app/main.py"]
    assert result["mentions"] == ["README.md:1"]
    assert (project / "README.md").read_text() == _FILES["README.md"]


# --- Degradation -----------------------------------------------------------------------------


async def test_an_unsure_use_refuses_and_names_its_line(project: Path) -> None:
    _write(project, {"src/app/zz.py": "def f(g):\n    return getattr(g, 'greet')\n"})
    before = _snapshot(project)

    result = await _dispatcher(project).execute("rename_symbol", _RENAME)

    assert "src/app/zz.py:2" in result["error"]
    assert _snapshot(project) == before


# --- Boundary --------------------------------------------------------------------------------


def test_a_caller_outside_the_write_grants_refuses(project: Path) -> None:
    grants = [
        FolderGrant(str(project / "src/app/greeter.py"), AccessMode.WRITE, recursive=False),
        FolderGrant(str(project / "src"), AccessMode.READ, recursive=True),
    ]
    before = _snapshot(project)

    result = _tool(project, grants).rename_symbol(**_RENAME)

    assert result.status == "error"
    assert "2 file(s)" in result.message
    assert "outside your write grants" in result.message
    assert _snapshot(project) == before


def test_spots_and_mentions_outside_the_read_grants_are_counted_not_named(project: Path) -> None:
    _write(project, {"secret/zz.py": "def f(g):\n    return g.greet()\n"})
    grants = [FolderGrant(str(project / "src"), AccessMode.FULL, recursive=True)]

    refused = _tool(project, grants).rename_symbol(**_RENAME)

    assert refused.status == "error"
    assert "secret" not in refused.message
    assert "1 in files outside your read grants" in refused.message

    (project / "secret/zz.py").unlink()
    done = _tool(project, grants).rename_symbol(**_RENAME)

    assert done.status == "success", done.message
    assert done.data["mentions"] == []
    assert done.data["mentions_outside_grants"] == 1


# --- Hostile ---------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["reviewer", "planner", "drafter"])
async def test_no_other_role_is_offered_or_allowed_the_rename(project: Path, role: str) -> None:
    dispatcher = _dispatcher(project, role)
    before = _snapshot(project)

    assert "rename_symbol" not in {d.name for d in dispatcher.available_tools()}
    result = await dispatcher.execute("rename_symbol", _RENAME)

    assert "error" in result
    assert _snapshot(project) == before


def test_the_implementer_is_offered_the_rename(project: Path) -> None:
    names = {d.name for d in _dispatcher(project).available_tools()}
    assert "rename_symbol" in names


@pytest.mark.parametrize(
    "path", ["../outside.py", "/etc/passwd.py", ".env/hook.py", "nowhere/x.py"]
)
async def test_a_path_outside_or_protected_changes_nothing(project: Path, path: str) -> None:
    _write(project, {".env/hook.py": "def greet():\n    pass\n"})
    before = _snapshot(project)

    result = await _dispatcher(project).execute(
        "rename_symbol", {"path": path, "symbol_name": "greet", "new_name": "welcome"}
    )

    assert "error" in result
    assert _snapshot(project) == before


@pytest.mark.parametrize("role", ["reviewer", "planner", "drafter"])
def test_the_tool_itself_refuses_another_role(project: Path, role: str) -> None:
    from specweaver.sandbox.code_structure.interfaces.tool import CodeStructureToolError

    executor = FileExecutor(project)
    tool = CodeStructureTool(
        CodeStructureAtom(executor),
        role,
        [FolderGrant(str(project), AccessMode.FULL, recursive=True)],
        executor=executor,
    )
    before = _snapshot(project)

    with pytest.raises(CodeStructureToolError, match="not allowed"):
        tool.rename_symbol(**_RENAME)
    assert _snapshot(project) == before


def test_a_code_file_the_role_cannot_read_is_not_named(project: Path) -> None:
    _write(project, {"secret/huge.py": "x = 1\n" * 400_000})
    grants = [FolderGrant(str(project / "src"), AccessMode.FULL, recursive=True)]

    result = _tool(project, grants).rename_symbol(**_RENAME)

    assert result.status == "error"
    assert "secret" not in result.message
    assert "1 in files outside your read grants" in result.message


def test_a_protected_caller_refuses_through_the_tool(project: Path) -> None:
    _write(project, {".env/hook.py": "from app.greeter import Greeter\nGreeter.greet(None, 'x')\n"})
    before = _snapshot(project)
    grants = [FolderGrant(str(project), AccessMode.FULL, recursive=True)]

    result = _tool(project, grants).rename_symbol(**_RENAME)

    assert result.status == "error"
    assert "protected" in result.message
    assert _snapshot(project) == before


@pytest.mark.parametrize(
    ("path", "with_executor"), [("src/app/greeter.py", False), ("src/x.xyz", True)]
)
def test_a_tool_that_cannot_rename_says_so(project: Path, path: str, with_executor: bool) -> None:
    executor = FileExecutor(project)
    tool = CodeStructureTool(
        CodeStructureAtom(executor),
        "implementer",
        [FolderGrant(str(project), AccessMode.FULL, recursive=True)],
        executor=executor if with_executor else None,
    )
    result = tool.rename_symbol(path, "Greeter.greet", "welcome")
    assert result.status == "error"
    assert "not supported" in result.message


_JVM = {
    "src/app/util/Greeter.kt": "package app.util\n\nopen class Greeter {\n    open fun greet(n: String) = n\n}\n",
    "src/app/Use.java": (
        "package app;\n\nimport app.util.Greeter;\n\n"
        'class Use extends Greeter {\n    String f() { return greet("x"); }\n}\n'
    ),
}


async def test_the_implementer_renames_a_kotlin_method_called_from_java(tmp_path: Path) -> None:
    # Proves: D-SENS-06 FR-8
    root = _write(tmp_path / "jvm", _JVM)
    result = await _dispatcher(root).execute(
        "rename_symbol",
        {"path": "src/app/util/Greeter.kt", "symbol_name": "Greeter.greet", "new_name": "welcome"},
    )

    assert "error" not in result, result
    assert "open fun welcome(n: String)" in (root / "src/app/util/Greeter.kt").read_text()
    assert 'return welcome("x");' in (root / "src/app/Use.java").read_text()


async def test_the_implementer_renames_a_typescript_class_across_modules(tmp_path: Path) -> None:
    # Proves: D-SENS-06 FR-8
    root = _write(
        tmp_path / "ts",
        {
            "src/greeter.ts": "export class Greeter {}\n",
            "src/app.ts": 'import { Greeter } from "./greeter";\nconst g = new Greeter();\n',
        },
    )
    result = await _dispatcher(root).execute(
        "rename_symbol",
        {"path": "src/greeter.ts", "symbol_name": "Greeter", "new_name": "Welcomer"},
    )

    assert "error" not in result, result
    assert (
        root / "src/app.ts"
    ).read_text() == 'import { Welcomer } from "./greeter";\nconst g = new Welcomer();\n'


async def test_the_implementer_renames_a_rust_function_across_modules(tmp_path: Path) -> None:
    # Proves: D-SENS-06 FR-8
    root = _write(
        tmp_path / "rs",
        {
            "Cargo.toml": '[package]\nname = "app"\n',
            "src/lib.rs": "mod util;\nmod run;\n",
            "src/util.rs": "pub fn total(a: u32) -> u32 { a }\n",
            "src/run.rs": "use crate::util::total;\nfn go() -> u32 { total(1) }\n",
        },
    )
    result = await _dispatcher(root).execute(
        "rename_symbol", {"path": "src/util.rs", "symbol_name": "total", "new_name": "add"}
    )

    assert "error" not in result, result
    assert (root / "src/run.rs").read_text() == "use crate::util::add;\nfn go() -> u32 { add(1) }\n"


async def test_the_implementer_renames_a_go_function_across_packages(tmp_path: Path) -> None:
    # Proves: D-SENS-06 FR-8
    root = _write(
        tmp_path / "go",
        {
            "go.mod": "module example.com/m\n",
            "util/util.go": "package util\n\nfunc Total(a int) int { return a }\n",
            "app/main.go": 'package main\n\nimport "example.com/m/util"\n\nfunc main() { util.Total(1) }\n',
        },
    )
    result = await _dispatcher(root).execute(
        "rename_symbol", {"path": "util/util.go", "symbol_name": "Total", "new_name": "Sum"}
    )

    assert "error" not in result, result
    assert "util.Sum(1)" in (root / "app/main.go").read_text()


async def test_the_implementer_renames_a_c_function_with_its_header(tmp_path: Path) -> None:
    # Proves: D-SENS-06 FR-8
    root = _write(
        tmp_path / "c",
        {
            "src/util.h": "int total(int a);\n",
            "src/util.c": '#include "util.h"\nint total(int a) { return a; }\n',
            "src/main.c": '#include "util.h"\nint main(void) { return total(1); }\n',
        },
    )
    result = await _dispatcher(root).execute(
        "rename_symbol", {"path": "src/util.c", "symbol_name": "total", "new_name": "sum"}
    )

    assert "error" not in result, result
    assert (root / "src/util.h").read_text() == "int sum(int a);\n"
    assert "return sum(1);" in (root / "src/main.c").read_text()
