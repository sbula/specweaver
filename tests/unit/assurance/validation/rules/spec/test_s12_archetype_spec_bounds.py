# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.spec.s12_archetype_spec_bounds import (
    S12ArchetypeSpecBoundsRule,
)


def test_s12_archetype_spec_bounds_pass() -> None:
    rule = S12ArchetypeSpecBoundsRule(required_headers={"h1": ["Main Title"], "h2": ["1. Purpose"]})
    rule.context = {
        "structure": '{"h1": ["Main Title"], "h2": ["1. Purpose", "2. Boundaries"], "h3": []}'
    }

    result = rule.check("spec content", Path("spec.md"))

    assert result.status == Status.PASS
    assert not result.findings


def test_s12_archetype_spec_bounds_missing_h2() -> None:
    rule = S12ArchetypeSpecBoundsRule(required_headers={"h2": ["1. Purpose", "3. Architecture"]})
    rule.context = {
        "structure": '{"h1": ["Main Title"], "h2": ["1. Purpose", "2. Boundaries"], "h3": []}'
    }

    result = rule.check("spec content", Path("spec.md"))

    assert result.status == Status.FAIL
    assert len(result.findings) == 1
    assert "Missing required <h2> header: '3. Architecture'" in result.findings[0].message


def test_s12_archetype_spec_bounds_no_payload() -> None:
    rule = S12ArchetypeSpecBoundsRule(required_headers={"h1": ["Main Title"]})
    rule.context = {}  # Missing structure payload

    result = rule.check("spec content", Path("spec.md"))

    assert result.status == Status.FAIL
    assert "Markdown AST payload missing or malformed" in result.message


def test_s12_archetype_spec_bounds_empty_no_requirements() -> None:
    rule = S12ArchetypeSpecBoundsRule()
    rule.context = {"structure": '{"h1": [], "h2": [], "h3": []}'}

    result = rule.check("spec content", Path("spec.md"))

    assert result.status == Status.PASS
