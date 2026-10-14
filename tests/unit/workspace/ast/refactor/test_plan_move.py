# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A file moved, and every import of it rewritten: all or none.

Proves: D-SENS-06 FR-10
Proves: D-SENS-06 FR-11

| Bucket | Case |
|---|---|
| Happy | Python absolute, relative and plain imports; TypeScript importers and the moved file; Go |
| Boundary | a submodule import `from app import greeter`; an index file; a `.js` specifier |
| Degradation | a module path as a string; a package `__init__.py`; a Go move to another folder |
| Hostile | a target that exists, another ending, another `context.yaml` module, a protected target |
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure
from specweaver.workspace.ast.refactor.move import MovePlan, plan_move
from specweaver.workspace.ast.refactor.rename import RenameRefusal, Spot

_PY = PythonCodeStructure()
_TS = TypeScriptCodeStructure()

_PYPROJ = {
    "context.yaml": "name: root\n",
    "app/__init__.py": "",
    "app/greeter.py": "from .util import shout\n\ndef greet(n):\n    return shout(n)\n",
    "app/util.py": "def shout(n):\n    return n.upper()\n",
    "app/main.py": "from app.greeter import greet\nimport app.greeter\nimport app.greeter as g\n\nprint(greet('a'), app.greeter.greet('b'), g.greet('c'))\n",
    "app/near.py": "from .greeter import greet\nfrom app import greeter\n",
    "README.md": "See app/greeter.py and app.greeter.\n",
}


def _plan(files: dict[str, str], path: str, new: str, parser=_PY) -> MovePlan:  # type: ignore[no-untyped-def]
    result = plan_move(files, path, new, parser)
    assert isinstance(result, MovePlan), result
    return result


def _refusal(files: dict[str, str], path: str, new: str, parser=_PY) -> RenameRefusal:  # type: ignore[no-untyped-def]
    result = plan_move(files, path, new, parser)
    assert isinstance(result, RenameRefusal), result
    return result


# --- Happy -----------------------------------------------------------------------------------


def test_python_importers_and_the_moved_file() -> None:
    plan = _plan(_PYPROJ, "app/greeter.py", "app/words/hello.py")

    assert plan.old_path == "app/greeter.py"
    assert plan.changes["app/words/hello.py"].startswith("from ..util import shout\n")
    assert plan.changes["app/main.py"] == (
        "from app.words.hello import greet\nimport app.words.hello\nimport app.words.hello as g\n\n"
        "print(greet('a'), app.words.hello.greet('b'), g.greet('c'))\n"
    )
    assert (
        plan.changes["app/near.py"]
        == "from .words.hello import greet\nfrom app.words import hello\n"
    )
    assert "app/greeter.py" not in plan.changes
    assert plan.mentions == [Spot("README.md", 1)]


def test_a_rename_in_the_same_folder() -> None:
    plan = _plan(_PYPROJ, "app/greeter.py", "app/hello.py")
    assert plan.changes["app/near.py"] == "from .hello import greet\nfrom app import hello\n"
    assert plan.changes["app/hello.py"].startswith("from .util import shout\n")


def test_typescript_importers_and_the_moved_file() -> None:
    files = {
        "src/greeter.ts": 'import { shout } from "./util";\nexport const greet = (n: string) => shout(n);\n',
        "src/util.ts": "export const shout = (n: string) => n;\n",
        "src/app.ts": 'import { greet } from "./greeter";\nexport { greet as g } from "./greeter.js";\n',
        "src/lib/deep.ts": 'import { greet } from "../greeter";\n',
    }
    plan = _plan(files, "src/greeter.ts", "src/words/hello.ts", _TS)

    assert plan.changes["src/words/hello.ts"].startswith('import { shout } from "../util";\n')
    assert (
        plan.changes["src/app.ts"]
        == 'import { greet } from "./words/hello";\nexport { greet as g } from "./words/hello.js";\n'
    )
    assert plan.changes["src/lib/deep.ts"] == 'import { greet } from "../words/hello";\n'


def test_go_renames_a_file_in_its_folder_and_changes_nothing_else() -> None:
    files = {
        "go.mod": "module m\n",
        "a/a.go": "package a\n\nfunc F() {}\n",
        "a/b.go": "package a\n\nfunc G() { F() }\n",
    }
    plan = _plan(files, "a/a.go", "a/first.go", GoCodeStructure())
    assert plan.changes == {"a/first.go": "package a\n\nfunc F() {}\n"}


# --- Boundary --------------------------------------------------------------------------------


def test_an_index_file_specifier() -> None:
    files = {
        "src/lib/index.ts": "export const x = 1;\n",
        "src/a.ts": 'import { x } from "./lib";\n',
    }
    plan = _plan(files, "src/lib/index.ts", "src/core/x.ts", _TS)
    assert plan.changes["src/a.ts"] == 'import { x } from "./core/x";\n'


# --- Degradation -----------------------------------------------------------------------------


def test_a_module_path_as_a_string_is_unsure() -> None:
    files = {
        **_PYPROJ,
        "app/dyn.py": "import importlib\nm = importlib.import_module('app.greeter')\n",
    }
    assert _refusal(files, "app/greeter.py", "app/hello.py").spots == [Spot("app/dyn.py", 2)]


def test_a_package_init_refuses() -> None:
    assert "__init__" in _refusal(_PYPROJ, "app/__init__.py", "app/start.py").reason


def test_a_go_move_to_another_folder_refuses() -> None:
    files = {"go.mod": "module m\n", "a/a.go": "package a\n\nfunc F() {}\n"}
    assert "folder" in _refusal(files, "a/a.go", "b/a.go", GoCodeStructure()).reason


# --- Hostile ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("new", "reason"),
    [
        ("app/util.py", "exists"),
        ("app/greeter.ts", "ending"),
        ("../x.py", "project"),
        ("/etc/x.py", "project"),
        (".env/x.py", "protected"),
        ("app/greeter.py", "exists"),
    ],
)
def test_a_target_that_cannot_be_used(new: str, reason: str) -> None:
    assert reason in _refusal(_PYPROJ, "app/greeter.py", new).reason


def test_a_target_in_another_context_yaml_module_refuses() -> None:
    files = {**_PYPROJ, "app/context.yaml": "name: app\n", "lib/context.yaml": "name: lib\n"}
    assert "module" in _refusal(files, "app/greeter.py", "lib/greeter.py").reason
