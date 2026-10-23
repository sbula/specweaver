# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A path the engine hands to a sandboxed atom never lies outside its root.

Proves: TECH-075 FR-8, TECH-075 NFR-3

`relative_to_root` → the project boundary (`project_file`) → the code structure atom and the QA
`source`. Real files and links; only the atom's `run` is spied on, to see what path it is given.

| Bucket | Case |
|---|---|
| Happy | a file inside answers its relative path; a generated module inside is the QA `source` |
| Boundary | the root itself; a relative path is read from the working folder; a link inside that points inside passes; with no project, the file's own folder is the root |
| Degradation | `add_payload` with a file outside the project logs a WARNING and never calls the atom |
| Hostile | an outside path, an escaping link, a null byte → refused; an outside module → no `source` |
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.handlers.archetype_pipelines import add_payload, relative_to_root
from specweaver.core.flow.handlers.qa_targets import generated_code
from specweaver.core.flow.handlers.review import _resolve_mentions
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture()
def world(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "proj"
    (project / "src").mkdir(parents=True)
    (project / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "secret.py").write_text("SECRET = 1\n", encoding="utf-8")
    (project / "src" / "escape.py").symlink_to(tmp_path / "secret.py")
    (project / "src" / "alias.py").symlink_to(project / "src" / "a.py")
    return project, tmp_path / "secret.py"


def test_a_file_inside_answers_its_relative_path(world: tuple[Path, Path]) -> None:
    project, _ = world

    assert relative_to_root(project / "src" / "a.py", project) == "src/a.py"
    assert relative_to_root(project / "src" / "alias.py", project) == "src/a.py"


def test_the_root_itself_is_inside(world: tuple[Path, Path]) -> None:
    project, _ = world

    assert relative_to_root(project, project) == "."


def test_a_relative_path_is_read_from_the_working_folder(
    world: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _ = world
    monkeypatch.chdir(project / "src")

    from pathlib import Path

    assert relative_to_root(Path("a.py"), project) == "src/a.py"


@pytest.mark.parametrize("where", ["outside", "escape", "dotdot", "nul"])
def test_a_path_outside_the_root_is_refused(world: tuple[Path, Path], where: str) -> None:
    project, secret = world
    path = {
        "outside": secret,
        "escape": project / "src" / "escape.py",
        "dotdot": project / ".." / "secret.py",
        "nul": project / "src" / "a\0.py",
    }[where]

    assert relative_to_root(path, project) is None


def test_the_structure_reader_never_gets_an_outside_path(
    world: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

    project, secret = world
    seen: list[str] = []

    def spy(self: CodeStructureAtom, context: dict) -> object:
        seen.append(context["path"])
        return SimpleNamespace(status=SimpleNamespace(value="FAILED"), exports={})

    monkeypatch.setattr(CodeStructureAtom, "run", spy)
    step = SimpleNamespace(params={})
    pipeline = SimpleNamespace(steps=[step])

    with caplog.at_level(logging.WARNING):
        add_payload(pipeline, secret, project, None, markers=True)

    assert seen == []
    assert step.params["ast_payload"] == {}
    assert any(
        "secret.py" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    )


def test_the_structure_reader_gets_an_inside_file(
    world: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

    project, _ = world
    seen: list[str] = []

    def spy(self: CodeStructureAtom, context: dict) -> object:
        seen.append(context["path"])
        return SimpleNamespace(status=SimpleNamespace(value="SUCCESS"), exports={"k": 1})

    monkeypatch.setattr(CodeStructureAtom, "run", spy)
    step = SimpleNamespace(params={})

    add_payload(SimpleNamespace(steps=[step]), project / "src" / "a.py", project, None)

    assert seen == ["src/a.py"]
    assert step.params["ast_payload"] == {"k": 1}


def _context(project: Path, output_dir: Path) -> RunContext:
    (project / "specs").mkdir(exist_ok=True)
    spec = project / "specs" / "a_spec.md"
    spec.write_text("# A\n", encoding="utf-8")
    return RunContext(project_path=project, spec_path=spec, output_dir=output_dir)


def test_a_generated_module_inside_is_the_qa_source(world: tuple[Path, Path]) -> None:
    project, _ = world

    assert generated_code(_context(project, project / "src")) == "src/a.py"


def test_a_generated_module_outside_is_no_qa_source(
    world: tuple[Path, Path], caplog: pytest.LogCaptureFixture
) -> None:
    project, secret = world
    outside = secret.parent / "out"
    outside.mkdir()
    (outside / "a.py").write_text("x = 2\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        source = generated_code(_context(project, outside))

    assert source == ""
    assert any(
        str(outside / "a.py") in r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING
    )


def test_a_module_not_yet_generated_is_no_qa_source(world: tuple[Path, Path]) -> None:
    project, _ = world
    (project / "src" / "a.py").unlink()

    assert generated_code(_context(project, project / "src")) == ""


def test_without_a_project_the_files_own_folder_is_the_root(
    world: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

    _, secret = world
    seen: list[str] = []

    def spy(self: CodeStructureAtom, context: dict) -> object:
        seen.append(context["path"])
        return SimpleNamespace(status=SimpleNamespace(value="FAILED"), exports={})

    monkeypatch.setattr(CodeStructureAtom, "run", spy)

    add_payload(SimpleNamespace(steps=[]), secret, None, None)

    assert seen == ["secret.py"]


def test_mentions_and_atom_paths_refuse_the_same_link(world: tuple[Path, Path]) -> None:
    """Two jobs, one rule: both ask the project boundary."""
    project, _ = world

    assert relative_to_root(project / "src" / "escape.py", project) is None
    assert _resolve_mentions(["src/escape.py"], project) == []
    assert relative_to_root(project / "src" / "alias.py", project) == "src/a.py"
    assert [m.original for m in _resolve_mentions(["src/alias.py"], project)] == ["src/alias.py"]
