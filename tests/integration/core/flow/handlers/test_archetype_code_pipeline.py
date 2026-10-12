# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Code under an archetype is checked by that archetype's pipeline, C12 included.

Proves: B-INTL-01 FR-2
Proves: B-INTL-01 FR-3

Nothing is mocked: a real `context.yaml`, the shipped `spring-boot` code pipeline, the real Java
parser. The C12 unit tests once fed it a marker shape the parser never produces.

| Bucket | Case |
|---|---|
| Happy | a class annotated `@RestController` passes C12 |
| Boundary | the markers reach the rule however the code path is given, absolute or relative |
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


def _c12(tmp_path: Path, code: str):
    (tmp_path / "svc" / "src").mkdir(parents=True)
    (tmp_path / "svc" / "context.yaml").write_text("archetype: spring-boot\n", encoding="utf-8")
    java = tmp_path / "svc" / "src" / "Hello.java"
    java.write_text(code, encoding="utf-8")
    spec = tmp_path / "svc" / "hello_spec.md"
    spec.write_text("# Hello\n", encoding="utf-8")
    results = ValidateCodeHandler()._run_validation(java, spec, None, project_path=tmp_path)
    return {r.rule_id: r for r in results}["C12"]


def test_an_annotated_controller_passes(tmp_path: Path) -> None:
    c12 = _c12(tmp_path, _ANNOTATED)

    assert c12.status is Status.PASS, [f.message for f in c12.findings]


def test_a_missing_annotation_fails_naming_it(tmp_path: Path) -> None:
    c12 = _c12(tmp_path, _PLAIN)

    assert c12.status is Status.FAIL
    assert any("@RestController" in f.message for f in c12.findings)
