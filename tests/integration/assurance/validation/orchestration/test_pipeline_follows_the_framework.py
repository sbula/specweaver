# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The validate steps pick the pipeline from the run's framework answer, as generation does.

Proves: TECH-079 FR-9

Real handler, real `context.yaml`, the shipped Spring Boot pipelines; the profile is the run's.

| Bucket | Case |
|---|---|
| Happy | a Java file with no archetype in a Spring Boot run gets C12; generation names the same framework |
| Boundary | a spec under `framework: spring-boot` gets the Spring Boot spec pipeline; the build file never picks a spec pipeline; a role archetype's own code pipeline still applies |
| Degradation | no profile: the folder alone decides |
| Hostile | a Python file in a Spring Boot run gets no C12 |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons.project_profile import ProjectProfile
from specweaver.core.flow.handlers.validation import ValidateCodeHandler

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_PLAIN = 'package demo;\n\npublic class Hello {\n    public String hi() { return "hi"; }\n}\n'
_BOOT = ProjectProfile("java", "maven", "spring-boot")


def _source(tmp_path: Path, name: str = "Hello.java", manifest: str | None = None) -> Path:
    folder = tmp_path / "svc"
    (folder / "src").mkdir(parents=True, exist_ok=True)
    if manifest is not None:
        (folder / "context.yaml").write_text(manifest, encoding="utf-8")
    source = folder / "src" / name
    source.write_text(_PLAIN if name.endswith(".java") else "def f():\n    return 1\n", "utf-8")
    (folder / "hello_spec.md").write_text("# Hello\n", encoding="utf-8")
    return source


def _rules(tmp_path: Path, source: Path, profile: ProjectProfile | None) -> set[str]:
    spec = tmp_path / "svc" / "hello_spec.md"
    results = ValidateCodeHandler()._run_validation(
        source, spec, None, project_path=tmp_path, profile=profile
    )
    return {r.rule_id for r in results or []}


def test_a_spring_boot_run_checks_java_with_c12(tmp_path: Path) -> None:
    from specweaver.workflows.implementation.frameworks import project_framework

    source = _source(tmp_path)

    assert "C12" in _rules(tmp_path, source, _BOOT)
    choice = project_framework(tmp_path, source, _BOOT)
    assert choice is not None and choice.key == "spring-boot"


def test_without_a_profile_the_folder_decides(tmp_path: Path) -> None:
    assert "C12" not in _rules(tmp_path, _source(tmp_path), None)
    assert "C12" in _rules(tmp_path, _source(tmp_path, manifest="framework: spring-boot\n"), None)


def test_a_python_file_in_a_spring_boot_run_gets_no_c12(tmp_path: Path) -> None:
    assert "C12" not in _rules(tmp_path, _source(tmp_path, "tool.py"), _BOOT)


def test_a_role_archetype_keeps_its_own_code_pipeline(tmp_path: Path) -> None:
    pipelines = tmp_path / ".specweaver" / "pipelines"
    pipelines.mkdir(parents=True)
    (pipelines / "validation_code_adapter.yaml").write_text(
        "name: validation_code_adapter\nsteps:\n  - name: c12\n    rule: C12\n"
        "    params:\n      required_markers: ['@Service']\n",
        encoding="utf-8",
    )

    rules = _rules(tmp_path, _source(tmp_path, manifest="archetype: adapter\n"), None)

    assert rules == {"C12"}


def test_a_spec_under_the_framework_key_gets_its_spec_pipeline(tmp_path: Path) -> None:
    from specweaver.assurance.validation.orchestration.archetype_pipelines import spec_pipeline

    _source(tmp_path, manifest="framework: spring-boot\n")
    spec = tmp_path / "svc" / "hello_spec.md"

    pipeline, key = spec_pipeline(spec, tmp_path)

    assert (pipeline.name, key) == ("validation_spec_spring-boot", "spring-boot")


def test_the_build_file_never_picks_a_spec_pipeline(tmp_path: Path) -> None:
    from specweaver.assurance.validation.orchestration.archetype_pipelines import spec_pipeline

    (tmp_path / "pom.xml").write_text("<g>org.springframework.boot</g>", encoding="utf-8")
    _source(tmp_path)

    pipeline, _key = spec_pipeline(tmp_path / "svc" / "hello_spec.md", tmp_path)

    assert pipeline.name == "validation_spec_default"
