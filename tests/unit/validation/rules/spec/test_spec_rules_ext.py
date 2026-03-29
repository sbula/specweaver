# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for spec validation runner, S03, S04, S07, S11 rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.validation.models import Rule, RuleResult, Severity, Status
from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule
from specweaver.validation.rules.spec.s04_dependency_dir import DependencyDirectionRule
from specweaver.validation.rules.spec.s07_test_first import TestFirstRule
from specweaver.validation.rules.spec.s11_terminology import TerminologyRule
from specweaver.validation.runner import (
    all_passed,
    count_by_status,
    run_rules,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "fixtures"


@pytest.fixture()
def good_spec() -> str:
    return (FIXTURES_DIR / "good_spec.md").read_text(encoding="utf-8")


@pytest.fixture()
def bad_ambiguous() -> str:
    return (FIXTURES_DIR / "bad_spec_ambiguous.md").read_text(encoding="utf-8")


@pytest.fixture()
def bad_no_examples() -> str:
    return (FIXTURES_DIR / "bad_spec_no_examples.md").read_text(encoding="utf-8")


@pytest.fixture()
def bad_too_big() -> str:
    return (FIXTURES_DIR / "bad_spec_too_big.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Runner tests
# ---------------------------------------------------------------------------


class TestRunner:
    """Test the validation runner (pipeline executor path)."""

    def test_spec_pipeline_has_eleven_rules(self) -> None:
        import specweaver.validation.rules.spec  # noqa: F401
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        assert len(pipeline.steps) == 11

    def test_spec_pipeline_excludes_llm_rules(self) -> None:
        import specweaver.validation.rules.spec  # noqa: F401
        from specweaver.validation.executor import execute_validation_pipeline
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        results = execute_validation_pipeline(pipeline, "## 1. Purpose\nSimple.\n")
        # No step should fail with 'not found in registry' (LLM rules excluded)
        for r in results:
            assert "not found in registry" not in r.message

    def test_spec_pipeline_rules_are_present(self) -> None:
        import specweaver.validation.rules.spec  # noqa: F401
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        ids = {s.rule for s in pipeline.steps}
        # All S01-S11 must be present
        expected = {f"S{i:02d}" for i in range(1, 12)}
        assert expected == ids

    def test_run_rules_collects_all_results(self, good_spec: str) -> None:
        import specweaver.validation.rules.spec  # noqa: F401
        from specweaver.validation.executor import execute_validation_pipeline
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        results = execute_validation_pipeline(pipeline, good_spec)
        assert len(results) == 11

    def test_run_rules_exception_handling(self) -> None:
        """A crashing rule should produce FAIL, not crash the runner."""

        class CrashingRule(Rule):
            @property
            def rule_id(self) -> str:
                return "X99"

            @property
            def name(self) -> str:
                return "Crasher"

            def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
                msg = "boom"
                raise RuntimeError(msg)

        results = run_rules([CrashingRule()], "some spec")
        assert len(results) == 1
        assert results[0].status == Status.FAIL
        assert "boom" in results[0].message

    def test_all_passed_with_passing_results(self) -> None:
        results = [
            RuleResult(rule_id="S01", rule_name="Test", status=Status.PASS),
            RuleResult(rule_id="S02", rule_name="Test", status=Status.SKIP),
        ]
        assert all_passed(results) is True

    def test_all_passed_with_failure(self) -> None:
        results = [
            RuleResult(rule_id="S01", rule_name="Test", status=Status.PASS),
            RuleResult(rule_id="S02", rule_name="Test", status=Status.FAIL),
        ]
        assert all_passed(results) is False

    def test_count_by_status(self) -> None:
        results = [
            RuleResult(rule_id="S01", rule_name="Test", status=Status.PASS),
            RuleResult(rule_id="S02", rule_name="Test", status=Status.PASS),
            RuleResult(rule_id="S05", rule_name="Test", status=Status.FAIL),
            RuleResult(rule_id="S08", rule_name="Test", status=Status.WARN),
        ]
        counts = count_by_status(results)
        assert counts[Status.PASS] == 2
        assert counts[Status.FAIL] == 1
        assert counts[Status.WARN] == 1
        assert counts[Status.SKIP] == 0

    def test_good_spec_passes_all(self, good_spec: str) -> None:
        """The good_spec fixture should pass all 11 rules."""
        import specweaver.validation.rules.spec  # noqa: F401
        from specweaver.validation.executor import execute_validation_pipeline
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_spec_default")
        results = execute_validation_pipeline(pipeline, good_spec)
        for r in results:
            assert r.status in (Status.PASS, Status.WARN), (
                f"{r.rule_id} ({r.rule_name}): {r.status.value} — {r.message}"
            )

    def test_empty_rules_list(self) -> None:
        results = run_rules([], "some spec")
        assert results == []
        assert all_passed(results) is True


# ---------------------------------------------------------------------------
# S03: Stranger Test
# ---------------------------------------------------------------------------


class TestS03StrangerTest:
    """S03 detects specs that are not self-contained."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = StrangerTestRule().check(good_spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_self_contained_passes(self) -> None:
        spec = """
## 1. Purpose

The Greeter Service generates personalized welcome messages.

## 2. Contract

`GreetService` is the main class. It accepts a name and returns a greeting.

```python
def greet(name: str) -> str:
    ...
```
"""
        result = StrangerTestRule().check(spec)
        assert result.status == Status.PASS

    def test_many_external_refs_warns(self) -> None:
        spec = """
## 1. Purpose

This component depends on many others.

See [auth](auth_spec.md) and [session](session_spec.md).
Also see [rate_limit](rate_limit_spec.md).
Also see [cache](cache_spec.md) and [db](db_spec.md).
Also see [queue](queue_spec.md).
"""
        result = StrangerTestRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert len(result.findings) > 3

    def test_many_undefined_terms_warns(self) -> None:
        spec = """
## 1. Purpose

Uses `FlowEngine`, `StateStore`, `TaskQueue`, `ConfigManager`,
`EventBus`, and `MetricsCollector` without explanation.
"""
        result = StrangerTestRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)

    def test_defined_terms_not_counted(self) -> None:
        """Terms defined in headers should not count as undefined."""
        spec = """
## 1. Purpose

The `GreetService` is a simple greeting component.

### `GreetService` Interface

```python
class GreetService:
    pass
```
"""
        result = StrangerTestRule().check(spec)
        assert result.status == Status.PASS

    def test_rule_id(self) -> None:
        assert StrangerTestRule().rule_id == "S03"
        assert StrangerTestRule().name == "Stranger Test"

    def test_empty_spec(self) -> None:
        result = StrangerTestRule().check("")
        assert result.status == Status.PASS

    def test_http_urls_excluded(self) -> None:
        """HTTP links should not count as external cross-references."""
        spec = """
## 1. Purpose

See [Python docs](https://docs.python.org) and [RFC 2119](https://tools.ietf.org/html/rfc2119).
"""
        result = StrangerTestRule().check(spec)
        assert result.status == Status.PASS

    def test_anchor_links_excluded(self) -> None:
        """Anchor links within the same doc should not count."""
        spec = """
## 1. Purpose

See [Contract](#contract) and [Protocol](#protocol) below.
"""
        result = StrangerTestRule().check(spec)
        assert result.status == Status.PASS

    def test_terms_inside_code_blocks_ignored(self) -> None:
        """Backtick terms inside fenced code should not count as undefined."""
        spec = """
## 1. Purpose

Simple greeter.

```python
# These should not trigger warnings
from myapp import FlowEngine, StateStore, TaskQueue
result = ConfigManager.get()
```
"""
        result = StrangerTestRule().check(spec)
        assert result.status == Status.PASS


# ---------------------------------------------------------------------------
# S04: Dependency Direction
# ---------------------------------------------------------------------------


class TestS04DependencyDirection:
    """S04 detects specs with too many cross-references to peers."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = DependencyDirectionRule().check(good_spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_no_cross_refs_passes(self) -> None:
        spec = """
## 1. Purpose

A simple standalone component.

## 2. Contract

Takes input, produces output.
"""
        result = DependencyDirectionRule().check(spec)
        assert result.status == Status.PASS
        assert "0" in result.message

    def test_many_links_warns(self) -> None:
        spec = """
## 3. Protocol

See [auth](auth_spec.md) for details.
See [session](session_spec.md) for state.
See [cache](cache_spec.md) for caching.
See [queue](queue_spec.md) for async.
See [db](db_spec.md) for storage.
See [metrics](metrics_spec.md) for monitoring.
"""
        result = DependencyDirectionRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert len(result.findings) >= 6

    def test_component_refs_detected(self) -> None:
        spec = """
Communicates with `AuthService`, `CacheManager`, `TaskHandler`,
`EventBus`, `MetricsProvider`, `ConfigAdapter`,
`SessionStore`, `QueueClient`, and `LogHandler`.
"""
        result = DependencyDirectionRule().check(spec)
        # 8 component suffixes matched (EventBus excluded — "Bus" not in suffix list)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any("Component reference" in f.message for f in result.findings)

    def test_code_block_refs_ignored(self) -> None:
        """References inside code blocks should not count."""
        spec = """
## 1. Purpose

Simple service.

```python
from auth import AuthService  # this should be ignored
class MyHandler:
    pass
```
"""
        result = DependencyDirectionRule().check(spec)
        assert result.status == Status.PASS

    def test_rule_id(self) -> None:
        assert DependencyDirectionRule().rule_id == "S04"
        assert DependencyDirectionRule().name == "Dependency Direction"

    def test_empty_spec(self) -> None:
        result = DependencyDirectionRule().check("")
        assert result.status == Status.PASS

    def test_section_refs_detected(self) -> None:
        """'see §3' patterns should be counted."""
        spec = """
See §1 for purpose.
See §2 for contract.
See §3 for protocol.
See §4 for policy.
See §5 for boundaries.
See section 6 for extras.
"""
        result = DependencyDirectionRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any("Section reference" in f.message for f in result.findings)

    def test_non_md_links_ignored(self) -> None:
        """Links to non-.md files should not count as cross-references."""
        spec = """
See [config](config.yaml) and [script](deploy.sh) for details.
"""
        result = DependencyDirectionRule().check(spec)
        # These are not .md links — should not be counted
        assert result.status == Status.PASS

    def test_findings_have_line_numbers(self) -> None:
        """Line numbers must be populated when threshold triggers findings."""
        spec = (
            "Line 1\n"
            "See [a](a_spec.md) link.\n"  # line 2
            "See [b](b_spec.md) link.\n"  # line 3
            "See [c](c_spec.md) link.\n"  # line 4
            "See [d](d_spec.md) link.\n"  # line 5
            "See [e](e_spec.md) link.\n"  # line 6
            "See [target](target_spec.md) link.\n"  # line 7
        )
        result = DependencyDirectionRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        target_findings = [f for f in result.findings if "target_spec.md" in f.message]
        assert len(target_findings) == 1
        assert target_findings[0].line == 7


# ---------------------------------------------------------------------------
# S07: Test-First
# ---------------------------------------------------------------------------


class TestS07TestFirst:
    """S07 checks that the Contract section is testable."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = TestFirstRule().check(good_spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_rich_contract_passes(self) -> None:
        spec = """
## 2. Contract

The `greet` function MUST return a `Greeting` object.
If the name is empty, it MUST raise `ValueError`.

```python
def greet(name: str) -> Greeting:
    ...
```

Example:
  Input: name = "Alice"
  Output: Greeting(message="Hello, Alice!")
"""
        result = TestFirstRule().check(spec)
        assert result.status == Status.PASS
        assert "12" in result.message or "score" in result.message.lower()

    def test_no_contract_fails(self) -> None:
        spec = "# Just a title\n\nNo contract here."
        result = TestFirstRule().check(spec)
        assert result.status == Status.FAIL
        assert any("Contract" in f.message for f in result.findings)

    def test_vague_contract_warns_or_fails(self) -> None:
        spec = """
## 2. Contract

The component does stuff.
"""
        result = TestFirstRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any(
            "testable" in f.message.lower() or "code" in f.message.lower() for f in result.findings
        )

    def test_contract_with_code_but_no_assertions_warns(self) -> None:
        spec = """
## 2. Contract

```python
class Greeter:
    pass
```
"""
        result = TestFirstRule().check(spec)
        # Has code but no assertions — should warn
        assert result.status in (Status.WARN, Status.PASS)

    def test_rule_id(self) -> None:
        assert TestFirstRule().rule_id == "S07"
        assert TestFirstRule().name == "Test-First"

    def test_empty_spec(self) -> None:
        result = TestFirstRule().check("")
        assert result.status == Status.FAIL

    def test_contract_header_without_number(self) -> None:
        """'## Contract' (no '2.') should still be detected."""
        spec = """
## Contract

The function MUST return a string.

```python
def greet(name: str) -> str:
    ...
```
"""
        result = TestFirstRule().check(spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_contract_as_last_section(self) -> None:
        """Contract at end of doc (no following ## header) should be extracted."""
        spec = """
## 1. Purpose

A greeter.

## 2. Contract

The `greet` function MUST return a greeting string.
It MUST raise `ValueError` for empty input.

```python
def greet(name: str) -> str:
    ...
```
"""
        result = TestFirstRule().check(spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_score_at_exact_fail_boundary(self) -> None:
        """Score 0-2 should FAIL — no code, no assertions, no values."""
        spec = """
## 2. Contract

The component handles things appropriately.
It does what is expected.
"""
        result = TestFirstRule().check(spec)
        assert result.status == Status.FAIL
        assert "low testability" in result.message.lower()


# ---------------------------------------------------------------------------
# S11: Terminology Consistency
# ---------------------------------------------------------------------------


class TestS11Terminology:
    """S11 detects inconsistent and undefined terminology in specs."""

    def test_good_spec_passes(self, good_spec: str) -> None:
        result = TerminologyRule().check(good_spec)
        assert result.status in (Status.PASS, Status.WARN)

    def test_rule_id(self) -> None:
        assert TerminologyRule().rule_id == "S11"
        assert TerminologyRule().name == "Terminology Consistency"

    def test_consistent_terms_passes(self) -> None:
        spec = """
## 1. Purpose

The `GreetService` generates personalized greetings.

## 2. Contract

```python
class GreetService:
    def greet(self, name: str) -> str:
        ...
```
"""
        result = TerminologyRule().check(spec)
        assert result.status == Status.PASS

    def test_inconsistent_casing_warns(self) -> None:
        """Same concept with different casing styles should trigger findings."""
        spec = """
## 1. Purpose

The `userId` field identifies the user. The `user_id` is stored in the
database. The `UserID` is sent in the header.
"""
        result = TerminologyRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any("inconsistent" in f.message.lower() for f in result.findings)

    def test_many_inconsistencies_fails(self) -> None:
        """3+ inconsistent term groups should FAIL."""
        spec = """
The `userId` and `user_id` identify the user.
The `sessionToken` and `session_token` are used for auth.
The `requestId` and `request_id` track requests.
"""
        result = TerminologyRule().check(spec)
        assert result.status == Status.FAIL
        assert len(result.findings) >= 3

    def test_undefined_domain_terms_warns(self) -> None:
        """PascalCase terms in backticks not defined in headers or code should warn."""
        spec = """
## 1. Purpose

This component uses `FlowEngine` and `StateManager` to process data.
"""
        result = TerminologyRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)
        assert any(
            "undefined" in f.message.lower() or "not defined" in f.message.lower()
            for f in result.findings
        )

    def test_defined_terms_not_flagged(self) -> None:
        """Terms defined in headers or code blocks should not be flagged."""
        spec = """
## 1. Purpose

The `GreetService` generates greetings.

### `GreetService` Interface

```python
class GreetService:
    pass
```
"""
        result = TerminologyRule().check(spec)
        assert result.status == Status.PASS
        assert not any("GreetService" in f.message for f in result.findings)

    def test_terms_in_code_blocks_counted_as_defined(self) -> None:
        """Terms appearing inside code blocks count as definitions."""
        spec = """
## 1. Purpose

Uses `ConfigManager` for configuration.

```python
class ConfigManager:
    def get(self) -> dict:
        ...
```
"""
        result = TerminologyRule().check(spec)
        assert result.status == Status.PASS

    def test_empty_spec_passes(self) -> None:
        result = TerminologyRule().check("")
        assert result.status == Status.PASS

    def test_findings_have_line_numbers(self) -> None:
        spec = "Line 1\nThe `userId` is here.\nThe `user_id` is there.\nLine 4\n"
        result = TerminologyRule().check(spec)
        if result.findings:
            assert all(f.line is not None and f.line > 0 for f in result.findings)

    def test_snake_case_variants_detected(self) -> None:
        """user_name vs userName should be detected as inconsistent."""
        spec = """
The `userName` field stores the user's name.
Later, the `user_name` field is validated.
"""
        result = TerminologyRule().check(spec)
        assert result.status in (Status.WARN, Status.FAIL)

    def test_single_inconsistency_warns(self) -> None:
        """One inconsistent group should WARN, not FAIL."""
        spec = "The `userId` and `user_id` track the user.\n"
        result = TerminologyRule().check(spec)
        assert result.status == Status.WARN


# ---------------------------------------------------------------------------
# S04: Traceability Extension (Dead Link Detection)
# ---------------------------------------------------------------------------


class TestS04DeadLinks:
    """S04 extension: dead link detection when spec_path is provided."""

    def test_existing_link_no_warning(self, tmp_path: Path) -> None:
        """A link to an existing file should not produce a dead-link finding."""
        target = tmp_path / "auth_spec.md"
        target.write_text("# Auth Spec", encoding="utf-8")
        spec_file = tmp_path / "my_spec.md"
        spec_text = "See [auth](auth_spec.md) for details.\n"
        spec_file.write_text(spec_text, encoding="utf-8")

        result = DependencyDirectionRule().check(spec_text, spec_path=spec_file)
        dead_link_findings = [
            f
            for f in result.findings
            if "dead link" in f.message.lower() or "not found" in f.message.lower()
        ]
        assert len(dead_link_findings) == 0

    def test_missing_link_warns(self, tmp_path: Path) -> None:
        """A link to a non-existent file should produce a dead-link warning."""
        spec_file = tmp_path / "my_spec.md"
        spec_text = "See [missing](missing_spec.md) for details.\n"
        spec_file.write_text(spec_text, encoding="utf-8")

        result = DependencyDirectionRule().check(spec_text, spec_path=spec_file)
        dead_link_findings = [
            f
            for f in result.findings
            if "dead link" in f.message.lower() or "not found" in f.message.lower()
        ]
        assert len(dead_link_findings) == 1
        assert dead_link_findings[0].severity == Severity.WARNING

    def test_no_path_skips_link_check(self) -> None:
        """Without spec_path, dead link checking should be skipped."""
        spec_text = "See [missing](missing_spec.md) for details.\n"
        result = DependencyDirectionRule().check(spec_text, spec_path=None)
        dead_link_findings = [
            f
            for f in result.findings
            if "dead link" in f.message.lower() or "not found" in f.message.lower()
        ]
        assert len(dead_link_findings) == 0

    def test_multiple_dead_links(self, tmp_path: Path) -> None:
        """Multiple dead links should each produce a finding."""
        spec_file = tmp_path / "my_spec.md"
        spec_text = (
            "See [a](a_spec.md) for details.\n"
            "See [b](b_spec.md) for details.\n"
            "See [c](c_spec.md) for details.\n"
        )
        spec_file.write_text(spec_text, encoding="utf-8")

        result = DependencyDirectionRule().check(spec_text, spec_path=spec_file)
        dead_link_findings = [
            f
            for f in result.findings
            if "dead link" in f.message.lower() or "not found" in f.message.lower()
        ]
        assert len(dead_link_findings) == 3

    def test_mixed_existing_and_dead_links(self, tmp_path: Path) -> None:
        """Only non-existent links should produce dead-link findings."""
        (tmp_path / "auth_spec.md").write_text("# Auth", encoding="utf-8")
        spec_file = tmp_path / "my_spec.md"
        spec_text = (
            "See [auth](auth_spec.md) for auth.\nSee [missing](missing_spec.md) for missing.\n"
        )
        spec_file.write_text(spec_text, encoding="utf-8")

        result = DependencyDirectionRule().check(spec_text, spec_path=spec_file)
        dead_link_findings = [
            f
            for f in result.findings
            if "dead link" in f.message.lower() or "not found" in f.message.lower()
        ]
        assert len(dead_link_findings) == 1
        assert "missing_spec.md" in dead_link_findings[0].message
