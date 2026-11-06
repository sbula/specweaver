# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every "which parser reads this file" asks one lookup, by ending, whatever its case.

Proves: TECH-079 FR-15

Real parsers, real files; each caller through its own public entry.

| Bucket | Case |
|---|---|
| Happy | `a.py` gets the Python parser in every lookup |
| Boundary | `A.PY`, `B.Java`, `x.TSX` get the same parser as their lower-case names; `.md` and `.sql` still have theirs; the registry is built once |
| Degradation | an ending no parser reads, or none, gets no parser |
| Hostile | a name that is only `.py`, or `py` with no dot, gets none; the registry cannot be changed by a caller |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers, parser_for
from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_NAMES = [
    ("a.py", PythonCodeStructure),
    ("A.PY", PythonCodeStructure),
    ("B.Java", JavaCodeStructure),
    ("x.TSX", TypeScriptCodeStructure),
]


@pytest.mark.parametrize(("name", "kind"), _NAMES)
def test_the_lookup_ignores_case(name: str, kind: type) -> None:
    assert isinstance(parser_for(name), kind)


@pytest.mark.parametrize("name", ["notes.md", "NOTES.MDX", "schema.SQL"])
def test_files_that_are_no_language_keep_their_parser(name: str) -> None:
    assert parser_for(name) is not None


@pytest.mark.parametrize("name", ["x.zz", "Makefile", ".py", "py", "a.py.bak"])
def test_a_name_no_parser_reads_gets_none(name: str) -> None:
    assert parser_for(name) is None


def test_the_registry_is_built_once_and_cannot_be_changed() -> None:
    first = get_default_parsers()

    assert get_default_parsers() is first
    with pytest.raises(TypeError):
        first[(".zz",)] = first[(".py", ".pyi")]  # type: ignore[index]


def test_an_injected_registry_is_asked_the_same_way() -> None:
    only_java = {(".java",): JavaCodeStructure()}

    assert isinstance(parser_for("A.JAVA", only_java), JavaCodeStructure)
    assert parser_for("a.py", only_java) is None


# --- each caller -------------------------------------------------------------------------------

_CODE = "def greet():\n    return 1\n"


@pytest.mark.parametrize("name", ["a.py", "A.PY"])
def test_the_graph_reads_and_collects_any_case(tmp_path: Path, name: str) -> None:
    from specweaver.graph.core.builder.orchestrator import GraphBuilder
    from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

    (tmp_path / name).write_text(_CODE, encoding="utf-8")

    data = extract_ast_dict(str(tmp_path / name))
    collected = GraphBuilder(engine=None).collect_files(tmp_path)  # type: ignore[arg-type]

    assert [c["name"] for c in data["children"]] == ["greet"]
    assert collected == {str(tmp_path / name)}


@pytest.mark.parametrize("name", ["a.py", "A.PY"])
def test_the_boundary_check_reads_any_case(tmp_path: Path, name: str) -> None:
    from specweaver.sandbox.language.core.boundary_check import check_boundaries

    (tmp_path / "context.yaml").write_text("name: app\nlevel: module\n", encoding="utf-8")
    (tmp_path / name).write_text("import os\n", encoding="utf-8")

    result = check_boundaries(tmp_path, name)

    assert "not a code file" not in result.note


@pytest.mark.parametrize("name", ["a.py", "A.PY"])
def test_rename_and_the_resolver_read_any_case(name: str) -> None:
    from specweaver.workspace.ast.refactor.python import PythonResolver
    from specweaver.workspace.ast.refactor.rename import resolver_for

    assert resolver_for(name) is PythonResolver
    resolver = PythonResolver({name: _CODE}, PythonCodeStructure())
    assert isinstance(resolver.parser_for(name), PythonCodeStructure)


@pytest.mark.parametrize("name", ["a.py", "A.PY"])
def test_the_code_structure_tools_read_any_case(tmp_path: Path, name: str) -> None:
    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
    from specweaver.sandbox.code_structure.interfaces.tool import _parser_for as tool_parser
    from specweaver.workspace.ast.refactor.files import _parser_for as files_parser

    atom = CodeStructureAtom(cwd=tmp_path)

    assert isinstance(atom._get_parser(name), PythonCodeStructure)
    assert isinstance(tool_parser(name), PythonCodeStructure)
    assert isinstance(files_parser(name), PythonCodeStructure)


def test_the_boundary_check_notes_a_file_no_parser_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.sandbox.language.core import boundary_check

    (tmp_path / "context.yaml").write_text("name: app\nlevel: module\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("import os\n", encoding="utf-8")
    monkeypatch.setattr(boundary_check, "parser_for", lambda _path, _parsers=None, **_k: None)

    result = boundary_check.check_boundaries(tmp_path, "a.py")

    assert result.violations == [] and "no parser reads a.py" in result.note
