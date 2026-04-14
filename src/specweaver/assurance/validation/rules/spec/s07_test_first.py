# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""S07: Test-First — checks that a spec's Contract section is concrete enough
   that tests can be derived from it without additional context.

Static heuristic: checks for testable patterns in the Contract section
(code blocks, input/output examples, assertions, specific values).
Full LLM analysis would attempt to generate a test skeleton.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Patterns indicating testable content
_ASSERTION_PATTERNS = [
    r"\bMUST\b",
    r"\bSHALL\b",
    r"\bSHOULD\b",
    r"\bMUST NOT\b",
    r"\bSHALL NOT\b",
    r"\braise\s+\w+Error\b",
    r"\braises?\b",
    r"\breturns?\s+\w+",
    r"\→\s*\w+",  # → SomeType
    r"->\s*\w+",  # -> SomeType
]

# Patterns for concrete values
_CONCRETE_VALUE_RE = re.compile(
    r"(?:"
    r'"[^"]+"|'  # quoted strings
    r"'[^']+'|"  # single-quoted strings
    r"\b\d+\b|"  # numbers
    r"\bTrue\b|"  # booleans
    r"\bFalse\b|"  #
    r"\bNone\b|"  #
    r"\bnull\b"  # null
    r")"
)


class TestFirstRule(Rule):
    """Check that Contract section is concrete enough to derive tests."""

    __test__ = False

    PARAM_MAP: ClassVar[dict[str, str]] = {
        "warn_threshold": "warn_score",
        "fail_threshold": "fail_score",
    }

    def __init__(
        self,
        warn_score: int = 6,
        fail_score: int = 3,
    ) -> None:
        self._warn_score = warn_score
        self._fail_score = fail_score

    @property
    def rule_id(self) -> str:
        return "S07"

    @property
    def name(self) -> str:
        return "Test-First"

    @property
    def requires_llm(self) -> bool:
        """Full test generation needs LLM, but static heuristic runs without."""
        return False

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        contract = _extract_contract(spec_text)

        if contract is None:
            return self._fail(
                "No Contract section found. Tests cannot be derived without a contract.",
                [
                    Finding(
                        message="Missing '## 2. Contract' or '## Contract' section",
                        severity=Severity.ERROR,
                    )
                ],
            )

        has_code, assertion_count, has_concrete, has_io = _analyse_contract(contract)
        findings = _collect_findings(has_code, assertion_count, has_concrete)

        # Score: how testable is this contract?
        testability_score = _testability_score(
            has_code,
            assertion_count,
            has_concrete,
            has_io,
        )

        if testability_score < self._fail_score:
            return self._fail(
                f"Contract has low testability (score {testability_score}/12). "
                "A test cannot be derived from this contract alone.",
                findings,
            )

        if testability_score < self._warn_score:
            return self._warn(
                f"Contract has moderate testability (score {testability_score}/12). "
                "Consider adding more concrete examples.",
                findings,
            )

        # ── Scenario section validation (Feature 3.28 SF-A) ──
        scenarios = _extract_scenarios(spec_text)
        if scenarios is None:
            return self._warn(
                f"Contract testability score: {testability_score}/12. "
                "No Scenarios section found — scenario generation will be skipped.",
                [
                    *findings,
                    Finding(
                        message="Missing '## Scenarios' section",
                        severity=Severity.WARNING,
                        suggestion="Add a '## Scenarios' section with YAML scenario definitions.",
                    ),
                ],
            )

        scenario_findings = _validate_scenario_yaml(scenarios)
        if scenario_findings:
            return self._warn(
                f"Contract testability score: {testability_score}/12. "
                "Scenarios section has structural issues.",
                findings + scenario_findings,
            )

        return self._pass(f"Contract testability score: {testability_score}/12")


def _analyse_contract(
    contract: str,
) -> tuple[bool, int, bool, bool]:
    """Analyse a contract section and return (has_code, assertion_count, has_concrete, has_io)."""
    code_blocks = contract.count("```")
    has_code = code_blocks >= 2  # at least one complete block

    assertion_count = 0
    for pattern in _ASSERTION_PATTERNS:
        assertion_count += len(re.findall(pattern, contract))

    has_concrete = bool(_CONCRETE_VALUE_RE.findall(contract))

    has_io = bool(
        re.search(
            r"(?:input|output|example|given|when|then|returns?)\s*:",
            contract,
            re.IGNORECASE,
        )
    )

    return has_code, assertion_count, has_concrete, has_io


def _collect_findings(
    has_code: bool,
    assertion_count: int,
    has_concrete: bool,
) -> list[Finding]:
    """Build the list of findings from contract analysis results."""
    findings: list[Finding] = []

    if not has_code:
        findings.append(
            Finding(
                message="No code blocks in Contract section",
                severity=Severity.WARNING,
                suggestion="Add interface definitions or examples as fenced code blocks.",
            )
        )

    if assertion_count == 0:
        findings.append(
            Finding(
                message="No testable assertions found (MUST, SHALL, raises, returns)",
                severity=Severity.WARNING,
                suggestion="Use RFC 2119 keywords (MUST, SHALL) to make requirements testable.",
            )
        )

    if not has_concrete:
        findings.append(
            Finding(
                message="No concrete values found (strings, numbers, booleans)",
                severity=Severity.WARNING,
                suggestion="Include specific inputs and expected outputs.",
            )
        )

    return findings


def _testability_score(
    has_code: bool,
    assertion_count: int,
    has_concrete: bool,
    has_io: bool,
) -> int:
    """Compute testability score (0-12) from contract analysis results."""
    score = 0
    if has_code:
        score += 3
    score += min(assertion_count, 5)  # cap at 5
    if has_concrete:
        score += 2
    if has_io:
        score += 2
    return score


def _extract_contract(text: str) -> str | None:
    """Extract the Contract section content from a spec."""
    # Match "## 2. Contract" or "## Contract"
    pattern = re.compile(
        r"^##\s+(?:2\.\s+)?Contract\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None

    start = match.end()
    # Find next ## header
    next_header = re.search(r"^##\s+", text[start:], re.MULTILINE)
    if next_header:
        return text[start : start + next_header.start()]
    return text[start:]


def _extract_scenarios(text: str) -> str | None:
    """Extract the Scenarios section content from a spec."""
    pattern = re.compile(
        r"^##\s+(?:\d+\.\s+)?Scenarios\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None

    start = match.end()
    next_header = re.search(r"^##\s+", text[start:], re.MULTILINE)
    if next_header:
        return text[start : start + next_header.start()]
    return text[start:]


_SCENARIO_REQUIRED_KEYS = frozenset(
    {"name", "function_under_test", "input_summary", "expected_behavior"}
)
_SCENARIO_VALID_CATEGORIES = frozenset({"happy", "error", "boundary"})


def _validate_scenario_yaml(scenarios_text: str) -> list[Finding]:
    """Validate that the Scenarios section contains valid YAML with expected schema.

    Expected schema per item (aligned with TestExpectation model):
      - name: str (required)
      - function_under_test: str (required)
      - input_summary: str (required)
      - expected_behavior: str (required)
      - category: str (optional, one of: happy|error|boundary)
    """
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    yaml = YAML(typ="safe")
    findings: list[Finding] = []

    # Extract YAML from code blocks
    code_blocks = re.findall(r"```(?:ya?ml)?\s*\n(.*?)```", scenarios_text, re.DOTALL)
    if not code_blocks:
        findings.append(
            Finding(
                message="Scenarios section has no YAML code blocks",
                severity=Severity.ERROR,
                suggestion="Add at least one ```yaml code block with scenario definitions.",
            )
        )
        return findings

    for block in code_blocks:
        try:
            data = yaml.load(block)
            if isinstance(data, list):
                for i, item in enumerate(data):
                    findings.extend(_validate_scenario_item(item, i))
            elif isinstance(data, dict):
                findings.extend(_validate_scenario_item(data, 0))
            else:
                findings.append(
                    Finding(
                        message=f"Scenario YAML must be a list or mapping, got: {type(data).__name__}",
                        severity=Severity.ERROR,
                    )
                )
        except YAMLError as exc:
            findings.append(
                Finding(
                    message=f"Invalid YAML in Scenarios section: {exc}",
                    severity=Severity.ERROR,
                    suggestion="Fix the YAML syntax in the scenario code block.",
                )
            )
    return findings


def _validate_scenario_item(item: Any, index: int) -> list[Finding]:
    """Validate a single scenario item against the expected schema."""
    findings: list[Finding] = []
    if not isinstance(item, dict):
        findings.append(
            Finding(
                message=f"Scenario item {index} must be a mapping, got: {type(item).__name__}",
                severity=Severity.ERROR,
            )
        )
        return findings

    missing = _SCENARIO_REQUIRED_KEYS - set(item.keys())
    if missing:
        findings.append(
            Finding(
                message=f"Scenario item {index} missing required keys: {sorted(missing)}",
                severity=Severity.ERROR,
                suggestion=f"Each scenario must have: {sorted(_SCENARIO_REQUIRED_KEYS)}",
            )
        )

    category = item.get("category")
    if category is not None and category not in _SCENARIO_VALID_CATEGORIES:
        findings.append(
            Finding(
                message=f"Scenario item {index} has invalid category '{category}'",
                severity=Severity.WARNING,
                suggestion=f"category must be one of: {sorted(_SCENARIO_VALID_CATEGORIES)}",
            )
        )
    return findings
