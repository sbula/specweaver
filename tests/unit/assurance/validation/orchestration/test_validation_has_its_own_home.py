# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Validation policy lives in `assurance/validation/orchestration`, and nothing in validation or
its API reaches into the flow engine's handlers for it.

Proves: TECH-082 FR-1, TECH-082 NFR-3

The dependency pointed the wrong way: the validation CLI and `POST /check` imported validation's
own policy from `core/flow/handlers`. The old module paths are gone, so a stale import or
`mock.patch` string fails loudly instead of patching nothing.

| Bucket | Case |
|---|---|
| Happy | the new home holds the moved functions; no module under `assurance/` or the check API imports the handlers |
| Boundary | an import inside a function body is still found |
| Degradation | a file that does not parse is named, not skipped |
| Hostile | an aliased `import specweaver.core.flow.handlers as h` is still found; the old paths do not import |
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[5] / "src" / "specweaver"
_HANDLERS = "specweaver.core.flow.handlers"
_OLD_PATHS = (
    "specweaver.core.flow.handlers.validation_hydrator",
    "specweaver.core.flow.handlers.archetype_pipelines",
    "specweaver.core.flow.engine.project_paths",
)
_NEW_HOME = {
    "specweaver.assurance.validation.orchestration.validation_hydrator": (
        "execute_validation_flow",
        "hydrate_code_validation_context",
        "discover_protocol_endpoints",
    ),
    "specweaver.assurance.validation.orchestration.archetype_pipelines": (
        "spec_pipeline",
        "code_pipeline",
        "own_pipeline",
        "add_payload",
        "relative_to_root",
        "archetype_of",
    ),
    "specweaver.assurance.validation.orchestration.project_paths": (
        "project_file",
        "ProjectPathError",
    ),
}


def _imports_of_handlers(path: Path) -> list[str]:
    """Each import of the handlers package in `path`, as `file:line`; `file:unparsable` on error."""
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
        if any(n == _HANDLERS or n.startswith(_HANDLERS + ".") for n in names):
            found.append(f"{path}:{node.lineno}")
    return found


def test_validation_and_its_api_never_import_the_handlers() -> None:
    files = [*sorted((_SRC / "assurance").rglob("*.py")), _SRC / "interfaces/api/v1/validation.py"]

    found = [hit for f in files for hit in _imports_of_handlers(f)]

    assert len(files) > 50
    assert found == []


@pytest.mark.parametrize("module", _OLD_PATHS)
def test_the_old_paths_do_not_import(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


@pytest.mark.parametrize(("module", "names"), list(_NEW_HOME.items()))
def test_the_new_home_holds_the_moved_functions(module: str, names: tuple[str, ...]) -> None:
    loaded = importlib.import_module(module)

    assert [n for n in names if not hasattr(loaded, n)] == []


def test_an_import_inside_a_function_is_found(tmp_path: Path) -> None:
    f = tmp_path / "lazy.py"
    f.write_text(
        "def run():\n    from specweaver.core.flow.handlers.x import y\n", encoding="utf-8"
    )

    assert _imports_of_handlers(f) == [f"{f}:2"]


def test_an_aliased_import_is_found(tmp_path: Path) -> None:
    f = tmp_path / "alias.py"
    f.write_text("import specweaver.core.flow.handlers as h\n", encoding="utf-8")

    assert _imports_of_handlers(f) == [f"{f}:1"]


def test_an_unparsable_file_is_named(tmp_path: Path) -> None:
    f = tmp_path / "broken.py"
    f.write_text("def (:\n", encoding="utf-8")

    assert _imports_of_handlers(f) == [f"{f}:unparsable"]


def test_a_neighbouring_name_is_not_the_handlers(tmp_path: Path) -> None:
    f = tmp_path / "near.py"
    f.write_text("from specweaver.core.flow.handlers_extra import z\n", encoding="utf-8")

    assert _imports_of_handlers(f) == []
