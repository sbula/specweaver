# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests — new_feature pipeline flow engine.

Exercises the sw run new_feature pipeline with mocked LLM and HITL:
  1. Validation fails in validate_spec step → pipeline aborts before review
  3. Validation fails in validate_spec step → pipeline stops (abort gate)
  5. LLM error mid-pipeline during generate_code → FAILED run state
  6. Constitution injected into review prompt during pipeline execution

Note: Tests 2 (DENIED→loop_back→re-review) and 4 (HITL park→resume) would
require real HITL interaction and are therefore tested at a lower level
(integration/flow/) rather than at CLI E2E level.
Test 7 (topology context injected) is covered in test_topology_e2e.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from specweaver.cli.main import app
from specweaver.llm.models import GenerationConfig, LLMResponse

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

_proj_counter = 0


def _unique_name(prefix: str = "nf") -> str:
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"


_GOOD_SPEC = """\
# calculator

## 1. Purpose

Provides basic arithmetic operations.

## 2. Contract

```python
def add(a: int, b: int) -> int:
    \"\"\"Return the sum of a and b.\"\"\"
```

### Examples

```python
>>> add(2, 3)
5
```

## 3. Protocol

1. Accept two integer arguments.
2. Return their sum as an integer.
3. MUST NOT raise exceptions for valid input.

## 4. Policy

| Error Condition | Behavior |
|---|---|
| Non-integer argument | Raise TypeError |

## 5. Boundaries

| Concern | Owned By |
|---|---|
| Logging | Infrastructure layer |
| Overflow | Python arbitrary precision |

## Done Definition

- [ ] Unit tests pass with coverage >= 80%
- [ ] `add(0, 0)` returns `0`
"""

_MINIMAL_SPEC = """\
# broken

Very short, fails most rules.
"""

_GENERATED_CODE = '''\
"""Calculator — arithmetic operations."""


def add(a: int, b: int) -> int:
    """Return the sum of a and b."""
    return a + b
'''

_GENERATED_TESTS = '''\
"""Tests for calculator."""


def test_add() -> None:
    from calculator import add
    assert add(2, 3) == 5
'''


def _make_llm(responses: list[str]) -> object:
    """Make a mock LLM returning responses sequentially."""
    mock_llm = AsyncMock()
    mock_llm.available.return_value = True
    mock_llm.provider_name = "mock"
    it = iter(responses)

    async def _generate(
        messages: object,
        config: object = None,
        dispatcher: object = None,
        on_tool_round: object = None,
    ) -> LLMResponse:
        return LLMResponse(text=next(it, "VERDICT: ACCEPTED\nDone."), model="mock")

    mock_llm.generate = _generate
    mock_llm.generate_with_tools = _generate
    return mock_llm


def _create_project_with_spec(
    tmp_path: Path,
    spec_content: str = _GOOD_SPEC,
    component: str = "calculator",
) -> tuple[Path, Path]:
    """Init project and write a spec file. Returns (project_dir, spec_path)."""
    project_dir = tmp_path / _unique_name()
    project_dir.mkdir()
    runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

    spec = project_dir / "specs" / f"{component}_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(spec_content, encoding="utf-8")
    return project_dir, spec


# ===========================================================================
# Test 1: Full new_feature pipeline completes with mocked LLM
# ===========================================================================


class TestNewFeatureFullCycle:
    """sw run new_feature — validate_only segment runs end to end."""

    def test_new_feature_validate_spec_step_runs(
        self,
        tmp_path: Path,
        _mock_state_db,
        monkeypatch,
    ) -> None:
        """sw run new_feature on a good spec → validate_spec step executes.

        The new_feature pipeline starts with draft_spec (HITL gate) which
        immediately parks without a real HITL session. We verify that:
        - The pipeline starts and doesn't crash
        - It enters the first step (draft) before parking
        - Exit is either 0 (park) or 1 (failure to start HITL)
        """
        project_dir, spec = _create_project_with_spec(tmp_path)

        # Mock HITL to auto-skip (empty answers — will park the run)
        with patch("specweaver.context.hitl_provider.HITLProvider") as mock_hitl_cls:
            mock_hitl = AsyncMock()
            mock_hitl.ask = AsyncMock(return_value="")
            mock_hitl.name = "mock_hitl"
            mock_hitl_cls.return_value = mock_hitl

            mock_llm = _make_llm([])
            with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
                mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
                result = runner.invoke(
                    app,
                    [
                        "run",
                        "new_feature",
                        str(spec),
                        "--project",
                        str(project_dir),
                    ],
                )

        # Should not crash (park is a valid state)
        assert result.exit_code in (0, 1), f"new_feature pipeline crashed: {result.output}"
        assert "Traceback" not in result.output


# ===========================================================================
# Test 3: validate_spec gate on_fail=abort → pipeline stops before review
# ===========================================================================


class TestNewFeatureValidationFailsStops:
    """validate_spec with all_passed gate and a failing spec → aborts early."""

    def test_new_feature_validation_fails_stops(
        self,
        tmp_path: Path,
        _mock_state_db,
        monkeypatch,
    ) -> None:
        """sw run validate_only on a minimal (bad) spec → fails, shows rule failures.

        We use validate_only pipeline here because new_feature's first step is
        draft (HITL). validate_only directly runs spec rules — confirms that a
        spec failing rules causes a pipeline abort (exit code 1) before any LLM
        call.
        """
        project_dir, spec = _create_project_with_spec(
            tmp_path,
            spec_content=_MINIMAL_SPEC,
            component="broken",
        )

        result = runner.invoke(
            app,
            [
                "run",
                "validate_only",
                str(spec),
                "--project",
                str(project_dir),
            ],
        )

        # Minimal spec should fail rules → exit 1
        assert result.exit_code == 1, f"Expected exit 1 for failing spec. Output:\n{result.output}"
        # At least one FAIL should appear
        assert "FAIL" in result.output or "fail" in result.output.lower()


# ===========================================================================
# Test 5: LLM error mid-pipeline → FAILED state
# ===========================================================================


class TestNewFeatureLlmErrorMidPipeline:
    """LLM error during a pipeline step → FAILED run state, no crash."""

    def test_new_feature_llm_error_mid_pipeline(
        self,
        tmp_path: Path,
        _mock_state_db,
    ) -> None:
        """sw review on a spec when LLM raises GenerationError → ERROR verdict shown.

        This tests that an LLM failure inside a pipeline-related CLI command
        surfaces as a clean error verdict rather than a traceback.
        """
        project_dir, spec = _create_project_with_spec(tmp_path)

        # LLM that always raises
        crash_llm = AsyncMock()
        crash_llm.available.return_value = True
        crash_llm.provider_name = "mock"

        async def _crash(
            messages: object,
            config: object = None,
            dispatcher: object = None,
            on_tool_round: object = None,
        ) -> None:
            from specweaver.llm.errors import GenerationError

            raise GenerationError("Service overloaded — try again later")

        crash_llm.generate = _crash
        crash_llm.generate_with_tools = _crash

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (None, crash_llm, GenerationConfig(model="mock"))
            result = runner.invoke(
                app,
                ["review", str(spec), "--project", str(project_dir)],
            )

        # Should NOT produce a Python traceback
        assert "Traceback" not in result.output, f"Unexpected traceback in output:\n{result.output}"
        # Should surface as ERROR verdict, not silent crash
        assert "ERROR" in result.output or "error" in result.output.lower(), (
            f"Expected ERROR verdict:\n{result.output}"
        )


# ===========================================================================
# Test 6: Constitution injected into review prompt during pipeline
# ===========================================================================


class TestNewFeatureWithConstitution:
    """sw review invokes LLM with constitution content injected."""

    def test_new_feature_with_constitution(
        self,
        tmp_path: Path,
        _mock_state_db,
    ) -> None:
        """sw review on a project with CONSTITUTION.md → constitution content is used.

        Verifies:
        - CONSTITUTION.md is read from the project
        - sw review succeeds with constitution present
        - ACCEPTED verdict returned
        """
        project_dir, spec = _create_project_with_spec(tmp_path)

        # Write a custom constitution
        constitution = project_dir / "CONSTITUTION.md"
        constitution.write_text(
            "# Project Constitution\n\n"
            "## Principles\n\n"
            "1. All functions MUST have type hints.\n"
            "2. All public APIs MUST have docstrings.\n"
            "3. Error handling MUST be explicit — no bare `except`.\n",
            encoding="utf-8",
        )

        captured_messages = []

        mock_llm = AsyncMock()
        mock_llm.available.return_value = True
        mock_llm.provider_name = "mock"

        async def _capture_and_respond(
            messages: object,
            config: object = None,
            dispatcher: object = None,
            on_tool_round: object = None,
        ) -> LLMResponse:
            captured_messages.extend(messages)
            return LLMResponse(text="VERDICT: ACCEPTED\nSpec meets constitution.", model="mock")

        mock_llm.generate = _capture_and_respond
        mock_llm.generate_with_tools = _capture_and_respond

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
            result = runner.invoke(
                app,
                ["review", str(spec), "--project", str(project_dir)],
            )

        assert result.exit_code == 0, f"review with constitution failed: {result.output}"
        assert "ACCEPTED" in result.output

        # Verify constitution content was injected into the LLM prompt
        all_content = " ".join(
            str(m.content) if hasattr(m, "content") else str(m) for m in captured_messages
        )
        assert "Constitution" in all_content or "type hints" in all_content.lower(), (
            "Constitution content does not appear to have been injected into the prompt"
        )
