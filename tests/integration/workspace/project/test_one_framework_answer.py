# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each file gets one framework answer: `framework:`, then a framework archetype, then the build file.

Proves: TECH-079 FR-10
Proves: TECH-079 FR-11

Real `context.yaml` files, real packaged and project evaluator schemas, the real profile reader.

| Bucket | Case |
|---|---|
| Happy | `framework:` alone; a framework archetype alone (warns to move it); the build file alone; generation follows the same answer |
| Boundary | `framework:` over archetype over build file; a role archetype is no framework; a file in another language gets none; a schema naming no languages covers any file; `spring` has a schema |
| Degradation | no profile (`sw check` on an undecided root): only the folder counts; a broken `context.yaml` is skipped; a project guide without a schema is not used, and a warning names the missing schema |
| Hostile | `framework:` naming no schema warns and is not used; a schema naming an unknown language is refused, naming it |
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from specweaver.commons.project_profile import ProjectProfile
from specweaver.workspace.project.frameworks import framework_for
from specweaver.workspace.project.project_profile import read_project_profile

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_JAVA = ProjectProfile("java", "maven")


def _folder(root: Path, manifest: str | None = None) -> Path:
    folder = root / "src" / "main" / "java" / "app"
    folder.mkdir(parents=True, exist_ok=True)
    if manifest is not None:
        (root / "src" / "context.yaml").write_text(manifest, encoding="utf-8")
    return folder / "Greeter.java"


def _key(root: Path, path: Path, profile: ProjectProfile | None = _JAVA) -> str | None:
    answer = framework_for(root, path, profile)
    return None if answer is None else answer.key


def test_the_framework_key_names_the_framework(tmp_path: Path) -> None:
    answer = framework_for(tmp_path, _folder(tmp_path, "framework: quarkus\n"), _JAVA)

    assert answer is not None
    assert (answer.key, answer.source) == ("quarkus", "framework")
    assert answer.languages == ("java", "kotlin")


def test_a_framework_archetype_still_works_and_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    code = _folder(tmp_path, "archetype: spring-boot\n")

    with caplog.at_level(logging.WARNING):
        answer = framework_for(tmp_path, code, _JAVA)
        framework_for(tmp_path, code, _JAVA)

    assert answer is not None
    assert (answer.key, answer.source) == ("spring-boot", "archetype")
    warnings = [r.getMessage() for r in caplog.records if "framework:" in r.getMessage()]
    assert len(warnings) == 1
    assert "spring-boot" in warnings[0]


def test_the_build_file_names_the_framework(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<g>org.springframework.boot</g>", encoding="utf-8")
    profile = read_project_profile(tmp_path)

    answer = framework_for(tmp_path, _folder(tmp_path), profile)

    assert answer is not None
    assert (answer.key, answer.source) == ("spring-boot", "build file")


def test_framework_wins_over_archetype_wins_over_build_file(tmp_path: Path) -> None:
    boot = ProjectProfile("java", "maven", "spring-boot")
    both = "archetype: quarkus\nframework: spring\n"

    assert _key(tmp_path, _folder(tmp_path, both), boot) == "spring"
    assert _key(tmp_path, _folder(tmp_path, "archetype: quarkus\n"), boot) == "quarkus"
    assert _key(tmp_path, _folder(tmp_path, "archetype: adapter\n"), boot) == "spring-boot"


def test_a_role_archetype_is_no_framework(tmp_path: Path) -> None:
    assert _key(tmp_path, _folder(tmp_path, "archetype: pure-logic\n")) is None


def test_a_file_in_another_language_gets_none(tmp_path: Path) -> None:
    _folder(tmp_path, "framework: spring-boot\n")
    python_file = tmp_path / "src" / "tool.py"

    assert _key(tmp_path, python_file, ProjectProfile("java", "maven", "spring-boot")) is None


def test_a_schema_naming_no_languages_covers_any_file(tmp_path: Path) -> None:
    _schema(tmp_path, "inhouse", "metadata:\n  framework: inhouse\n")

    assert _key(tmp_path, _folder(tmp_path, "framework: inhouse\n")) == "inhouse"


def test_spring_has_a_schema_with_its_languages(tmp_path: Path) -> None:
    answer = framework_for(tmp_path, _folder(tmp_path, "framework: spring\n"), _JAVA)

    assert answer is not None
    assert answer.languages == ("java", "kotlin")


def test_without_a_profile_only_the_folder_counts(tmp_path: Path) -> None:
    assert _key(tmp_path, _folder(tmp_path, "framework: quarkus\n"), None) == "quarkus"
    assert _key(tmp_path, _folder(tmp_path, "archetype: adapter\n"), None) is None


def test_a_broken_context_file_is_skipped(tmp_path: Path) -> None:
    boot = ProjectProfile("java", "maven", "spring-boot")

    assert _key(tmp_path, _folder(tmp_path, "framework: [unclosed\n"), boot) == "spring-boot"


def test_a_framework_key_with_no_schema_warns_and_is_not_used(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    boot = ProjectProfile("java", "maven", "spring-boot")

    with caplog.at_level(logging.WARNING):
        key = _key(tmp_path, _folder(tmp_path, "framework: micronaut\n"), boot)

    assert key == "spring-boot"
    assert any(".specweaver/evaluators/micronaut.yaml" in r.getMessage() for r in caplog.records)


def test_a_schema_naming_an_unknown_language_is_refused(tmp_path: Path) -> None:
    _schema(tmp_path, "odd", 'metadata:\n  supported_languages: ["cobol"]\n')

    with pytest.raises(ValueError, match=r"odd.*cobol"):
        framework_for(tmp_path, _folder(tmp_path, "framework: odd\n"), _JAVA)


def _schema(root: Path, name: str, text: str) -> None:
    folder = root / ".specweaver" / "evaluators"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.yaml").write_text(text, encoding="utf-8")


# --- generation follows the same answer ----------------------------------------------------------


def test_generation_takes_the_framework_key(tmp_path: Path) -> None:
    from specweaver.workflows.implementation.frameworks import project_framework

    choice = project_framework(tmp_path, _folder(tmp_path, "framework: quarkus\n"), _JAVA)

    assert choice is not None
    assert (choice.key, choice.guide.name, choice.source) == ("quarkus", "Quarkus", "framework")


def test_a_project_guide_without_a_schema_is_not_used(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.workflows.implementation.frameworks import project_framework

    guide = tmp_path / ".specweaver" / "frameworks" / "micronaut.md"
    guide.parent.mkdir(parents=True)
    guide.write_text("---\nname: Micronaut\n---\n# Code\nBeans.\n# Tests\nT.\n", "utf-8")

    with caplog.at_level(logging.WARNING):
        choice = project_framework(tmp_path, _folder(tmp_path, "archetype: micronaut\n"), _JAVA)

    assert choice is None
    assert any(".specweaver/evaluators/micronaut.yaml" in r.getMessage() for r in caplog.records)


def test_the_nearest_framework_key_wins(tmp_path: Path) -> None:
    code = _folder(tmp_path, "framework: spring\n")
    (code.parent / "context.yaml").write_text("framework: quarkus\n", encoding="utf-8")

    assert _key(tmp_path, code) == "quarkus"


def test_a_schema_whose_metadata_is_not_a_table_covers_any_file(tmp_path: Path) -> None:
    _schema(tmp_path, "loose", "metadata: just text\n")

    assert _key(tmp_path, _folder(tmp_path, "framework: loose\n")) == "loose"


# --- the agent tools and the skeleton read `framework:` too -------------------------------------


def test_the_agent_tools_follow_the_framework_key(tmp_path: Path) -> None:
    from specweaver.sandbox.code_structure.interfaces.tool import CodeStructureTool
    from specweaver.sandbox.dispatcher import ToolDispatcher
    from specweaver.sandbox.security import WorkspaceBoundary

    _schema(tmp_path, "inhouse", "intents:\n  hide: [list_symbols]\n")
    (tmp_path / "context.yaml").write_text("archetype: adapter\nframework: inhouse\n", "utf-8")

    dispatcher = ToolDispatcher.create_standard_set(
        WorkspaceBoundary(roots=[tmp_path]), role="implementer", allowed_tools=["ast"]
    )

    tool = next(t for t in dispatcher._interfaces if isinstance(t, CodeStructureTool))
    assert tool._hidden_intents == ["list_symbols"]


def test_the_skeleton_follows_the_framework_key(tmp_path: Path) -> None:
    from unittest.mock import patch

    from specweaver.core.flow.handlers.skeleton_assembler import (
        evaluate_and_fetch_skeleton_context,
    )
    from specweaver.core.flow.run_state.run_context import RunContext

    code = _folder(tmp_path, "archetype: adapter\nframework: quarkus\n")
    code.write_text("class Greeter {}\n", encoding="utf-8")
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "greeter_spec.md")

    with patch("specweaver.core.flow.handlers.skeleton_assembler.CodeStructureAtom") as atom:
        evaluate_and_fetch_skeleton_context(context, [code])

    assert atom.call_args.kwargs["active_archetype"] == "quarkus"
