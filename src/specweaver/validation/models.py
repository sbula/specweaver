# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Validation models — Rule, RuleResult, Finding interfaces.

All rules implement the Rule ABC. Results use a uniform RuleResult/Finding
structure so the runner and reporters don't care which rule produced them.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pathlib import Path


class Severity(enum.StrEnum):
    """Finding severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Status(enum.StrEnum):
    """Rule result status."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


class Finding(BaseModel):
    """A single issue found by a rule."""

    message: str
    line: int | None = None
    severity: Severity = Severity.ERROR
    suggestion: str | None = None


class RuleResult(BaseModel):
    """Result of running a single rule."""

    rule_id: str
    rule_name: str
    status: Status
    findings: list[Finding] = Field(default_factory=list)
    message: str = ""


class Rule(ABC):
    """Abstract base class for all validation rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique identifier, e.g. 'S01' or 'C03'."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name, e.g. 'One-Sentence Test'."""
        ...

    @property
    def requires_llm(self) -> bool:
        """Whether this rule requires an LLM adapter. Default: False."""
        return False

    @abstractmethod
    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        """Run the rule against spec content.

        Args:
            spec_text: Full text content of the spec file.
            spec_path: Optional path to the spec file (for rules that
                need to resolve relative references).

        Returns:
            RuleResult with status and any findings.
        """
        ...

    def _pass(self, message: str = "") -> RuleResult:
        """Convenience: create a PASS result."""
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            status=Status.PASS,
            message=message,
        )

    def _fail(self, message: str, findings: list[Finding] | None = None) -> RuleResult:
        """Convenience: create a FAIL result."""
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            status=Status.FAIL,
            findings=findings or [],
            message=message,
        )

    def _warn(self, message: str, findings: list[Finding] | None = None) -> RuleResult:
        """Convenience: create a WARN result."""
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            status=Status.WARN,
            findings=findings or [],
            message=message,
        )

    def _skip(self, message: str = "") -> RuleResult:
        """Convenience: create a SKIP result."""
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            status=Status.SKIP,
            message=message,
        )
