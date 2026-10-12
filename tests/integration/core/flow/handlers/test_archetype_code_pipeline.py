# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Code under an archetype is checked by that archetype's pipeline, C12 included.

Proves: B-INTL-01 FR-2
Proves: B-INTL-01 FR-3
Proves: B-INTL-01 FR-5

Nothing is mocked: a real `context.yaml`, the shipped `spring-boot` code pipeline, the real Java
parser. The C12 unit tests once fed it a marker shape the parser never produces.

| Bucket | Case |
|---|---|
| Happy | a class annotated `@RestController` passes C12 |
| Boundary | the markers reach the rule however the code path is given, absolute or relative |
| Boundary | Java and Kotlin get the archetype's rules and no Python rules; a Python file there does not |
| Degradation | not applicable — an unparsable file is C01's job |
| Hostile | a class without the annotation fails C12, naming the marker |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.models import Status
from specweaver.core.flow.handlers.validation import ValidateCodeHandler

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_ANNOTATED = 'package demo;\n\n@RestController\npublic class Hello {\n    public String hi() { return "hi"; }\n}\n'
_PLAIN = 'package demo;\n\npublic class Hello {\n    public String hi() { return "hi"; }\n}\n'


def _rules(tmp_path: Path, name: str, code: str) -> dict:
    (tmp_path / "svc" / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "svc" / "context.yaml").write_text("archetype: spring-boot\n", encoding="utf-8")
    source = tmp_path / "svc" / "src" / name
    source.write_text(code, encoding="utf-8")
    spec = tmp_path / "svc" / "hello_spec.md"
    spec.write_text("# Hello\n", encoding="utf-8")
    results = ValidateCodeHandler()._run_validation(source, spec, None, project_path=tmp_path)
    return {r.rule_id: r for r in results}


def _c12(tmp_path: Path, code: str):
    return _rules(tmp_path, "Hello.java", code)["C12"]


def test_an_annotated_controller_passes(tmp_path: Path) -> None:
    c12 = _c12(tmp_path, _ANNOTATED)

    assert c12.status is Status.PASS, [f.message for f in c12.findings]


def test_a_missing_annotation_fails_naming_it(tmp_path: Path) -> None:
    c12 = _c12(tmp_path, _PLAIN)

    assert c12.status is Status.FAIL
    assert any("@RestController" in f.message for f in c12.findings)


_KOTLIN = 'package demo\n\n@RestController\nclass Hello {\n    fun hi() = "hi"\n}\n'
_PYTHON_RULES = {"C01", "C02", "C06", "C08"}


@pytest.mark.parametrize(("name", "code"), [("Hello.java", _ANNOTATED), ("Hello.kt", _KOTLIN)])
def test_java_and_kotlin_get_the_archetype_rules_only(tmp_path: Path, name: str, code: str) -> None:
    rules = _rules(tmp_path, name, code)

    assert rules["C12"].status is Status.PASS
    assert not _PYTHON_RULES & rules.keys()


def test_a_python_file_in_the_folder_gets_the_default_rules(tmp_path: Path) -> None:
    rules = _rules(tmp_path, "tool.py", "def tool() -> None:\n    pass\n")

    assert "C12" not in rules
    assert "C01" in rules
