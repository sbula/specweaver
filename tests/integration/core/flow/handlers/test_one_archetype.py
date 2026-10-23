# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A file's archetype is found one way: its nearest `context.yaml`, wherever the engine asks.

Proves: TECH-077 FR-6

Real `context.yaml` files; the code structure atom is spied on only to see which archetype it is
built with.

| Bucket | Case |
|---|---|
| Happy | a file under `service/` (`spring-boot`) gets `spring-boot` from the run context, the archetype pipelines and the skeleton step |
| Boundary | a project with no `context.yaml` is `generic` everywhere; a file named relative to the project is judged inside it |
| Degradation | an unreadable `context.yaml` gives `generic` and a WARNING |
| Hostile | a topology that claims another archetype does not override the file's own `context.yaml` |
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.handlers import context_assembler
from specweaver.core.flow.handlers.archetype_pipelines import archetype_of
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "context.yaml").write_text("archetype: generic\n", encoding="utf-8")
    service = tmp_path / "service"
    service.mkdir()
    (service / "context.yaml").write_text("archetype: spring-boot\n", encoding="utf-8")
    (service / "orders_spec.md").write_text("# Orders\n", encoding="utf-8")
    (service / "orders.py").write_text("def order():\n    return 1\n", encoding="utf-8")
    return tmp_path


def _skeleton_archetypes(
    context: RunContext, files: list[Path], monkeypatch: pytest.MonkeyPatch
) -> list[str]:
    built: list[str] = []

    class _Atom:
        def __init__(self, *, cwd: Path, active_archetype: str, parsers: object) -> None:
            built.append(active_archetype)

        def run(self, _request: dict) -> object:
            return SimpleNamespace(status=SimpleNamespace(value="FAILED"), exports={})

    monkeypatch.setattr(context_assembler, "CodeStructureAtom", _Atom)
    context_assembler.evaluate_and_fetch_skeleton_context(context, files)
    return built


def test_every_place_answers_the_files_own_archetype(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = project / "service" / "orders_spec.md"
    context = RunContext(project_path=project, spec_path=spec)

    assert context._read_archetype() == "spring-boot"
    assert archetype_of(project / "service" / "orders.py", project) == "spring-boot"
    assert _skeleton_archetypes(context, [project / "service" / "orders.py"], monkeypatch) == [
        "spring-boot"
    ]


def test_no_context_yaml_is_generic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "a_spec.md")

    assert context._read_archetype() == "generic"
    assert _skeleton_archetypes(context, [tmp_path / "a.py"], monkeypatch) == ["generic"]


def test_an_unreadable_context_yaml_is_generic_and_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "context.yaml").write_text("archetype: [unclosed\n", encoding="utf-8")
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "a_spec.md")

    with caplog.at_level(logging.WARNING):
        assert context._read_archetype() == "generic"
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_a_topology_does_not_override_the_files_archetype(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = project / "service" / "orders_spec.md"
    context = RunContext(project_path=project, spec_path=spec)
    context.graph = context.graph.model_copy(
        update={"topology": SimpleNamespace(archetype="adapter")}
    )

    assert _skeleton_archetypes(context, [project / "service" / "orders.py"], monkeypatch) == [
        "spring-boot"
    ]


def test_a_relative_file_path_is_judged_inside_the_project(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    context = RunContext(project_path=project, spec_path=project / "service" / "orders_spec.md")

    assert _skeleton_archetypes(context, [Path("service/orders.py")], monkeypatch) == [
        "spring-boot"
    ]
