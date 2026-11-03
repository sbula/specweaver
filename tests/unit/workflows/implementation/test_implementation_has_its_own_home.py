# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Task files, framework choice and contract rendering live in `workflows/implementation`, and the
moved code neither detects the language itself nor reaches back into the flow engine.

Proves: TECH-082 FR-3, TECH-082 NFR-3

The caller passes the language (`core.flow.engine.run_language`), so the moved code needs no
`sandbox` import. The old module paths are gone, so a stale import or `mock.patch` string fails
loudly instead of patching nothing.

| Bucket | Case |
|---|---|
| Happy | the new home holds the moved names; the moved files import no `sandbox` and no `core.flow` |
| Boundary | an import inside a function body is still found |
| Degradation | a file that does not parse is named, not skipped |
| Hostile | an aliased `import specweaver.sandbox as s` is still found; the old paths do not import |
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[4] / "src" / "specweaver"
_HOME = _SRC / "workflows" / "implementation"
_BARRED = ("specweaver.sandbox", "specweaver.core.flow")
_MOVED = ("task_files.py", "frameworks.py", "contract_renderers.py")
_OLD_PATHS = (
    "specweaver.core.flow.engine.task_files",
    "specweaver.core.flow.engine.frameworks",
    "specweaver.core.flow.handlers.contract_renderers",
)
_NEW_HOME = {
    "specweaver.workflows.implementation.task_files": ("TaskFiles", "task_files_for", "task_brief"),
    "specweaver.workflows.implementation.frameworks": ("FrameworkChoice", "project_framework"),
    "specweaver.workflows.implementation.contract_renderers": (
        "extract_contract",
        "extract_methods",
        "render_contract_file",
    ),
}


def _barred_imports(path: Path) -> list[str]:
    """Each import of a barred package in `path`, as `file:line`; `file:unparsable` on error."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # expected: named, so an unreadable file cannot pass as clean
        return [f"{path}:unparsable"]
    found = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        if any(n == b or n.startswith(b + ".") for n in names for b in _BARRED):
            found.append(f"{path}:{node.lineno}")
    return found


def test_the_moved_code_imports_no_sandbox_and_no_flow() -> None:
    files = [_HOME / name for name in _MOVED]

    assert [f for f in files if not f.is_file()] == []
    assert [hit for f in files for hit in _barred_imports(f)] == []


@pytest.mark.parametrize("module", _OLD_PATHS)
def test_the_old_paths_do_not_import(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


@pytest.mark.parametrize(("module", "names"), list(_NEW_HOME.items()))
def test_the_new_home_holds_the_moved_names(module: str, names: tuple[str, ...]) -> None:
    loaded = importlib.import_module(module)

    assert [n for n in names if not hasattr(loaded, n)] == []


def test_an_import_inside_a_function_is_found(tmp_path: Path) -> None:
    f = tmp_path / "lazy.py"
    f.write_text(
        "def run():\n    from specweaver.sandbox.language.core.detect import x\n", encoding="utf-8"
    )

    assert _barred_imports(f) == [f"{f}:2"]


def test_an_aliased_import_is_found(tmp_path: Path) -> None:
    f = tmp_path / "alias.py"
    f.write_text("import specweaver.core.flow.engine as e\n", encoding="utf-8")

    assert _barred_imports(f) == [f"{f}:1"]


def test_an_unparsable_file_is_named(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def (:\n", encoding="utf-8")

    assert _barred_imports(f) == [f"{f}:unparsable"]


def test_a_neighbouring_name_is_not_barred(tmp_path: Path) -> None:
    f = tmp_path / "near.py"
    f.write_text("from specweaver.sandboxed import z\n", encoding="utf-8")

    assert _barred_imports(f) == []
