# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for C12: Archetype Code Bounds."""

from __future__ import annotations

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c12_archetype_code_bounds import (
    C12ArchetypeCodeBoundsRule,
)


def test_c12_pass_no_params():
    """If no params given, should pass vacuously."""
    rule = C12ArchetypeCodeBoundsRule()
    rule.context = {"framework_markers": {"Api": {"decorators": ["RestController"]}}}
    result = rule.check("")
    assert result.status == Status.PASS


def test_c12_pass_required_marker_present():
    """Should pass if required marker is in framework_markers."""
    rule = C12ArchetypeCodeBoundsRule(required_markers=["@RestController"])
    rule.context = {"framework_markers": {"Api": {"decorators": ["RestController"], "extends": []}}}
    result = rule.check("")
    assert result.status == Status.PASS


def test_c12_fail_required_marker_missing():
    """Should fail if required marker is missing."""
    rule = C12ArchetypeCodeBoundsRule(required_markers=["@RestController"])
    rule.context = {"framework_markers": {"Repo": {"decorators": ["Repository"], "extends": []}}}
    result = rule.check("")
    assert result.status == Status.FAIL
    assert len(result.findings) == 1
    assert "@RestController" in result.findings[0].message


def test_c12_fail_forbidden_marker_present():
    """Should fail if a forbidden marker is present."""
    # Example: A Domain entity model shouldn't have HTTP logic
    rule = C12ArchetypeCodeBoundsRule(forbidden_markers=["@RestController"])
    rule.context = {"framework_markers": {"Api": {"decorators": ["RestController"], "extends": []}}}
    result = rule.check("")
    assert result.status == Status.FAIL
    assert len(result.findings) == 1
    assert "@RestController" in result.findings[0].message


def test_c12_pass_forbidden_marker_missing():
    """Should pass if a forbidden marker is absent."""
    rule = C12ArchetypeCodeBoundsRule(forbidden_markers=["@RestController"])
    rule.context = {"framework_markers": {"Repo": {"decorators": ["Repository"], "extends": []}}}
    result = rule.check("")
    assert result.status == Status.PASS


def test_c12_context_missing():
    """Should handle cases gracefully where framework_markers isn't in context."""
    rule = C12ArchetypeCodeBoundsRule(required_markers=["@RestController"])
    rule.context = {}  # Empty context or code unsupported by treesitter
    result = rule.check("")
    assert result.status == Status.FAIL
    assert len(result.findings) == 1
    assert "@RestController" in result.findings[0].message


def test_c12_a_supertype_counts_as_a_marker():
    """`extends` is a marker too, so a required base class is enforced like an annotation."""
    rule = C12ArchetypeCodeBoundsRule(required_markers=["BaseService"])
    rule.context = {"framework_markers": {"Svc": {"decorators": [], "extends": ["BaseService"]}}}
    assert rule.check("").status == Status.PASS
