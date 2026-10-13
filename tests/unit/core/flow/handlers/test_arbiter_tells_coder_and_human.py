# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the arbiter hands on: the coder gets its own stack trace; a person gets the unclear clause.

Proves: B-FLOW-01 FR-9
Proves: B-FLOW-01 FR-10

| Bucket | Case |
|---|---|
| Happy | a code bug: the coder's feedback holds the frames of its code and the error; an unclear clause parks naming both readings and the spec |
| Boundary | the failure is an assertion inside the check itself: no trace at all |
| Degradation | resumed with the spec unchanged: parks again, no model call; spec edited: the round runs again |
| Hostile | a kept frame naming a banned word drops the whole trace; a Java trace keeps only code frames |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.arbiter import ArbitrateVerdictHandler, code_trace
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext, RunHandle
from specweaver.sandbox.language.core.python.stack_trace_filter import PythonStackTraceFilter
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

_RAISED_IN_CODE = """scenarios/generated/test_greet_scenarios.py:12: in test_happy_greet
    result = greet("Bob")
src/greet.py:3: in greet
    raise ValueError("no salutation configured")
E   ValueError: no salutation configured
"""

_ASSERTED_IN_CHECK = """scenarios/generated/test_greet_scenarios.py:14: in test_happy_greet
    assert result == "Hello, Bob"
E   AssertionError: assert 'Hi Bob' == 'Hello, Bob'
"""

_JAVA = """java.lang.IllegalArgumentException: empty name
\tat com.demo.Greeter.greet(Greeter.java:7)
\tat scenarios.generated.GreeterScenarios.happy(GreeterScenarios.java:21)
"""

_STEP = PipelineStep(
    name="arbitrate_verdict", action=StepAction.ARBITRATE, target=StepTarget.VERDICT
)

_AMBIGUOUS = {
    "verdict": "spec_ambiguity",
    "spec_clause": "FR-2",
    "interpretations": ["an empty name raises ValueError", "an empty name greets 'Hello, '"],
    "coding_feedback": "",
    "scenario_feedback": "",
}


def _context(tmp_path: Path, verdict: dict[str, object], *, trace: str = _RAISED_IN_CODE):
    spec = tmp_path / "greet_spec.md"
    spec.write_text("# Greet\n\n## FR-2\n\nAn empty name is handled.\n", encoding="utf-8")
    llm = AsyncMock()
    llm.generate.return_value = json.dumps(verdict)
    context = RunContext(project_path=tmp_path, spec_path=spec)
    context.run = RunHandle(run_id="r1", step_name="arbitrate_verdict")
    context.model = ModelAccess(llm_router=FixedRouter(llm))
    context.feedback = {
        "scenario_test_failures": {
            "total": 2,
            "passed": 1,
            "failed": 1,
            "errors": 0,
            "failures": [
                {
                    "nodeid": "scenarios/generated/test_greet_scenarios.py::test_happy_greet",
                    "message": "ValueError: no salutation configured",
                    "stacktrace": trace,
                }
            ],
        }
    }
    return context, llm


# --- FR-9: the coder's own stack trace ------------------------------------


def test_the_trace_keeps_the_codes_frames_and_its_error() -> None:
    # Proves: B-FLOW-01 FR-9
    kept = code_trace(_RAISED_IN_CODE, PythonStackTraceFilter())
    assert "src/greet.py:3: in greet" in kept
    assert "E   ValueError: no salutation configured" in kept
    assert "scenarios" not in kept
    assert "test_happy_greet" not in kept


def test_an_assertion_inside_the_check_gives_no_trace() -> None:
    assert code_trace(_ASSERTED_IN_CHECK, PythonStackTraceFilter()) == ""


def test_a_java_trace_keeps_only_code_frames() -> None:
    class _JavaFilter(PythonStackTraceFilter):
        def is_scenario_frame(self, line: str) -> bool:
            return "scenarios.generated" in line

    kept = code_trace(_JAVA, _JavaFilter())
    assert "Greeter.greet(Greeter.java:7)" in kept
    assert "IllegalArgumentException: empty name" in kept
    assert "GreeterScenarios" not in kept


def test_a_banned_word_in_a_kept_frame_drops_the_trace() -> None:
    leaky = _RAISED_IN_CODE.replace("src/greet.py", "src/test_helpers.py")
    assert code_trace(leaky, PythonStackTraceFilter()) == ""


async def test_a_code_bug_hands_the_coder_its_trace(tmp_path: Path) -> None:
    # Proves: B-FLOW-01 FR-9
    verdict = {
        "verdict": "code_bug",
        "spec_clause": "FR-1",
        "coding_feedback": "greet MUST return the salutation for a valid name.",
        "scenario_feedback": "",
    }
    context, _ = _context(tmp_path, verdict)

    result = await ArbitrateVerdictHandler().execute(_STEP, context)

    assert result.status == StepStatus.FAILED
    message = context.feedback["generate_code"]["findings"]["results"][0]["message"]
    assert message.startswith("greet MUST return the salutation for a valid name.")
    assert "src/greet.py:3: in greet" in message
    assert "ValueError: no salutation configured" in message
    for hidden in ("scenario", "test_happy_greet", "generated/"):
        assert hidden not in message.lower()


# --- FR-10: an unclear clause goes to a person -----------------------------


async def test_an_unclear_clause_parks_naming_both_readings_and_the_spec(tmp_path: Path) -> None:
    # Proves: B-FLOW-01 FR-10
    context, _ = _context(tmp_path, _AMBIGUOUS)

    result = await ArbitrateVerdictHandler().execute(_STEP, context)

    assert result.status == StepStatus.WAITING_FOR_INPUT
    for part in ("FR-2", "an empty name raises ValueError", "an empty name greets 'Hello, '"):
        assert part in result.error_message
    assert str(context.spec_path) in result.error_message
    assert "resume" in result.error_message
    assert result.output["interpretations"] == _AMBIGUOUS["interpretations"]


async def test_resumed_with_the_spec_unchanged_it_parks_again_without_a_model_call(
    tmp_path: Path,
) -> None:
    # Proves: B-FLOW-01 FR-10
    context, llm = _context(tmp_path, _AMBIGUOUS)
    parked = await ArbitrateVerdictHandler().execute(_STEP, context)
    resumed, llm = _context(tmp_path, _AMBIGUOUS)
    resumed.feedback = {}  # evidence is not kept across sessions
    resumed.run = resumed.run.model_copy(update={"step_records": [_record(parked)]})

    again = await ArbitrateVerdictHandler().execute(_STEP, resumed)

    assert again.status == StepStatus.WAITING_FOR_INPUT
    assert "unchanged" in again.error_message
    llm.generate.assert_not_called()


async def test_resumed_after_the_spec_was_edited_the_round_runs_again(tmp_path: Path) -> None:
    # Proves: B-FLOW-01 FR-10
    context, _ = _context(tmp_path, _AMBIGUOUS)
    parked = await ArbitrateVerdictHandler().execute(_STEP, context)
    resumed, llm = _context(tmp_path, _AMBIGUOUS)
    resumed.spec_path.write_text("# Greet\n\n## FR-2\n\nAn empty name raises ValueError.\n")
    resumed.feedback = {}
    resumed.run = resumed.run.model_copy(update={"step_records": [_record(parked)]})

    again = await ArbitrateVerdictHandler().execute(_STEP, resumed)

    assert again.status == StepStatus.FAILED  # the gate loops back to a fresh round
    assert "edited" in again.error_message
    llm.generate.assert_not_called()


def _record(result: object) -> dict[str, object]:
    return {"step_name": "arbitrate_verdict", "status": "running", "result": result.model_dump()}
