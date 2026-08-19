# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The schemas this tool SHIPS unroll the annotations they claim to.

Proves: TECH-065 FR-3

`B-INTL-02`'s own tests build a fixture schema and fixture markers, so both sides agree by
construction and a mismatch between the shipped keys and what the parsers actually extract cannot
appear. That is why an annotation carrying arguments never matched for as long as it did: half of
every shipped schema was unreachable and every test was green.

This drives `load_evaluator_schemas()` — the real files under
`workflows/evaluators/frameworks/` — with the marker text the parsers really produce. It is the test
that could have caught the defect, so it is the one that keeps it closed.
"""

from __future__ import annotations

import pytest

from specweaver.sandbox.language.core.evaluator import SchemaEvaluator
from specweaver.workflows.evaluators.loader import load_evaluator_schemas

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def evaluator() -> SchemaEvaluator:
    return SchemaEvaluator(load_evaluator_schemas())


@pytest.mark.parametrize(
    ("language", "framework", "category", "marker", "expected"),
    [
        # The three cases the ticket measured as broken.
        ("java", "spring-boot", "decorators", 'GetMapping("/orders/{id}")', "RequestMethod.GET"),
        ("java", "spring-boot", "decorators", 'PostMapping("/orders")', "RequestMethod.POST"),
        ("rust", "actix-web", "decorators", 'get("/orders")', "Actix HTTP GET"),
        # The argument-less subset, which always worked and must keep working.
        ("java", "spring-boot", "decorators", "RestController", "@Controller"),
        # A shipped key that ALREADY carries arguments: exact match must still win.
        ("rust", "actix-web", "decorators", "derive(Clone)", "impl Clone"),
    ],
)
def test_a_shipped_annotation_unrolls(
    evaluator: SchemaEvaluator,
    language: str,
    framework: str,
    category: str,
    marker: str,
    expected: str,
) -> None:
    out = evaluator.evaluate_markers(language, framework, {category: [marker]})

    assert expected in out, f"{marker} unrolled to {out!r}"


def test_an_annotation_no_schema_declares_stays_silent(evaluator: SchemaEvaluator) -> None:
    """The control. Matching on a bare name must not turn every unknown annotation into a hit."""
    out = evaluator.evaluate_markers("java", "spring-boot", {"decorators": ['Nonsense("/x")']})

    assert out == ""
