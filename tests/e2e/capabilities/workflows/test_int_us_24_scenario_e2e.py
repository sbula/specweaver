# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-24 Verifiable Proof (FR-7): behavioral scenario verification, end to end.

REAL surfaces throughout `sw run scenario_integration`: real contract extraction, real
dual-pipeline fan-out, real ScenarioGenerator (scripted LLM JSON), real converter emitting
REAL test bodies, real pytest subprocess executing them, real arbiter judging real QA
evidence, real gates/loop_back/park state. The coding sub-pipeline's internal quality loop
(US-2/US-3 proven territory) is doubled at the boundary — its GenerateCodeHandler double is
the scripted implementer that writes deterministically BUGGY-then-FIXED source, dramatizing
the US-24 sentence: unit-green but business-wrong, caught by independent verification.

  E1 happy: COMPLETED, exit 0, ZERO arbitration LLM calls, scenario tests genuinely ran
  E2 code_bug: buggy impl FAILS real scenario tests -> arbiter -> loop -> fixed -> green
  E3 scenario_error: arbiter blames scenarios -> regeneration WITH the prior-verdict block
  E4 spec_ambiguity: park (exit 0 + resume hint + PARKED row + evidence retained in-run)
  E5 retries exhausted: bounded stop, non-zero, arbiter message surfaced
  E6 zero-collected: empty ScenarioSet -> loud failure (SF-01 guard chain end-to-end)
  E7 park -> resume: evidence is NOT persisted -> honest arbiter error trips the
     loop_back and the park HEALS through a fresh verification round (COMPLETED)
  E8 generator retry exhaustion: garbage JSON x3 -> loud pipeline failure
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _now_iso
from specweaver.core.flow.handlers.validation import ValidateTestsHandler
from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

pytestmark = pytest.mark.e2e

# --------------------------------------------------------------------------- #
# Fixtures: spec, implementations, scenario payloads, verdicts                 #
# --------------------------------------------------------------------------- #

SPEC_BODY = """# Greet Service Spec

## 1. Purpose

The greet service returns a salutation string for a given user name.

Example:

```python
greet("Ada")  # returns "Hello Ada"
```

Error path: when the name is empty, `farewell` raises `ValueError` with the message
`name required`.

Done when: `greet` returns the exact salutation for valid names (FR-1) and `farewell`
raises `ValueError` for empty names (FR-2), verified by unit tests.

## 2. Contract

```python
def greet(name: str) -> str:
    \"\"\"Return the salutation for the given name.\"\"\"

def farewell(name: str) -> str:
    \"\"\"Return the farewell; raises ValueError on empty name.\"\"\"
```

## 3. Scenarios

```yaml
scenarios:
  - req_id: FR-1
    behavior: greeting includes the salutation
  - req_id: FR-2
    behavior: empty name is rejected
```

## Done Definition

- [ ] `greet` returns the exact salutation for valid names (FR-1)
- [ ] `farewell` raises `ValueError` for empty names (FR-2)
"""

CORRECT_IMPL = """\
def greet(name):
    return f"Hello {name}"


def farewell(name):
    if not name:
        raise ValueError("name required")
    return f"Bye {name}"
"""

# Business-wrong but unit-green in the (doubled) coding pipeline: the
# salutation is dropped. Only independent scenario verification catches it.
WRONG_IMPL = CORRECT_IMPL.replace('return f"Hello {name}"', "return name")


def _scenario_set_json(greet_expected_prefix: str = "Hello") -> str:
    return json.dumps(
        {
            "spec_path": "specs/llm_authored_path.md",  # LLM data — must NOT steer the loader
            "contract_path": "contracts/greet_contract.py",
            "scenarios": [
                {
                    "name": "greet_bob",
                    "description": "greeting includes salutation",
                    "function_under_test": "greet",
                    "req_id": "FR-1",
                    "category": "happy",
                    "input_summary": "plain name",
                    "inputs": {"name": "Bob"},
                    "expected_behavior": "salutation included",
                    "expected_output": f"{greet_expected_prefix} Bob",
                },
                {
                    "name": "greet_ada",
                    "description": "greeting includes salutation",
                    "function_under_test": "greet",
                    "req_id": "FR-1",
                    "category": "happy",
                    "input_summary": "plain name",
                    "inputs": {"name": "Ada"},
                    "expected_behavior": "salutation included",
                    "expected_output": f"{greet_expected_prefix} Ada",
                },
                {
                    "name": "farewell_empty_raises",
                    "description": "empty name rejected",
                    "function_under_test": "farewell",
                    "req_id": "FR-2",
                    "category": "error",
                    "input_summary": "empty name",
                    "inputs": {"name": ""},
                    "expected_behavior": "raises ValueError",
                    "expected_output": None,
                },
            ],
            "reasoning": "scripted",
        }
    )


GOOD_SET = _scenario_set_json()
# Scenarios asserting the WRONG expectation ("Hi Bob") — the scenario side's fault.
BAD_EXPECTATION_SET = _scenario_set_json(greet_expected_prefix="Hi")
EMPTY_SET = json.dumps(
    {"spec_path": "s", "contract_path": "c", "scenarios": [], "reasoning": "empty"}
)

CODE_BUG_VERDICT = json.dumps(
    {
        "verdict": "code_bug",
        "spec_clause": "FR-1",
        "coding_feedback": "The implementation must include the salutation required by FR-1.",
        "scenario_feedback": "",
    }
)
SCENARIO_ERROR_VERDICT = json.dumps(
    {
        "verdict": "scenario_error",
        "spec_clause": "FR-1",
        "coding_feedback": "",
        "scenario_feedback": "The expected salutation per FR-1 is 'Hello <name>', not 'Hi <name>'.",
    }
)
AMBIGUITY_VERDICT = json.dumps(
    {
        "verdict": "spec_ambiguity",
        "spec_clause": "FR-1",
        "coding_feedback": "",
        "scenario_feedback": "",
    }
)


# --------------------------------------------------------------------------- #
# Scripted LLM adapter: TWO in-contract branches, everything else is a bug     #
# --------------------------------------------------------------------------- #


class ScenarioWorldAdapter:
    """Scenario-generation prompts pop from `scenario_payloads` (reuse-last when
    drained — loop rounds regenerate); arbitration prompts pop from `verdicts`
    (never reused — every arbitration must be deliberately scripted). Any other
    LLM call is out-of-contract and fails loud."""

    model = "scripted-1"
    provider_name = "scripted"

    def __init__(self, scenario_payloads: list[str], verdicts: list[str]):
        self.scenario_payloads = list(scenario_payloads)
        self.verdicts = list(verdicts)
        self.arb_calls = 0
        self.scen_calls = 0
        self.scen_prompts: list[str] = []

    async def generate(self, messages, config=None, *args, **kwargs) -> LLMResponse:
        flat = str(messages)
        if "arbitration agent" in flat:
            self.arb_calls += 1
            if not self.verdicts:
                raise AssertionError("Unscripted arbitration LLM call")
            return LLMResponse(text=self.verdicts.pop(0), model=self.model)
        if "Respond with a JSON object" in flat:
            self.scen_calls += 1
            self.scen_prompts.append(flat)
            if len(self.scenario_payloads) > 1:
                return LLMResponse(text=self.scenario_payloads.pop(0), model=self.model)
            return LLMResponse(text=self.scenario_payloads[0], model=self.model)
        raise AssertionError(f"Out-of-contract LLM call: {flat[:160]}")

    async def generate_with_tools(self, messages, config, dispatcher, **kwargs) -> LLMResponse:
        return await self.generate(messages, config)


# --------------------------------------------------------------------------- #
# US-3-boundary doubles                                                        #
# --------------------------------------------------------------------------- #


def _passed(output: dict) -> StepResult:
    return StepResult(
        status=StepStatus.PASSED, output=output, started_at=_now_iso(), completed_at=_now_iso()
    )


async def _ok_execute(self, step, context) -> StepResult:
    return _passed({"stubbed": "US-3-boundary (proven territory)"})


async def _accepted_execute(self, step, context) -> StepResult:
    return _passed({"verdict": "accepted", "stubbed": "US-3-boundary"})


class ImplementerState:
    """The scripted implementer: writes deterministic source per loop round and
    consumes verdict feedback exactly like the real handler (pop-once)."""

    def __init__(self, impls: list[str]):
        self.impls = list(impls)
        self.received_feedback: list = []


def _make_implementer(state: ImplementerState):
    async def _execute(self, step, context) -> StepResult:
        state.received_feedback.append(context.feedback.pop(step.name, None))
        impl = state.impls.pop(0) if len(state.impls) > 1 else state.impls[0]
        stem = context.spec_path.stem.replace("_spec", "")
        out = context.project_path / "src" / f"{stem}.py"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(impl, encoding="utf-8")
        return _passed({"generated_path": str(out), "round": len(state.received_feedback)})

    return _execute


_REAL_VALIDATE_TESTS = ValidateTestsHandler.execute


def _make_validate_tests_wrapper(record: list):
    """run_tests (coding sub-pipeline, US-3 territory) -> stub PASS;
    run_scenario_tests -> the REAL handler (real QA runner, real pytest)."""

    async def _execute(self, step, context) -> StepResult:
        if step.name == "run_scenario_tests":
            result = await _REAL_VALIDATE_TESTS(self, step, context)
            record.append(result)
            return result
        return _passed({"passed": 1, "failed": 0, "errors": 0, "total": 1, "failures": []})

    return _execute


# --------------------------------------------------------------------------- #
# World assembly                                                               #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    return data_dir


def _settings_mock():
    settings = MagicMock()
    settings.llm.model = "scripted-1"
    settings.llm.temperature = 0.2
    settings.llm.max_output_tokens = 4096
    from specweaver.core.config.settings import SandboxSettings

    settings.sandbox = SandboxSettings()
    return settings


def _init_project(tmp_path: Path, name: str) -> Path:
    project_dir = tmp_path / name
    project_dir.mkdir()
    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0, result.output
    # D-VAL-02 project-local mechanical-only spec battery (INT-US-02 pattern).
    pipelines = project_dir / ".specweaver" / "pipelines"
    pipelines.mkdir(parents=True, exist_ok=True)
    (pipelines / "validation_spec_default_orchestrator.yaml").write_text(
        "name: validation_spec_default_orchestrator\n"
        "description: Mechanical-only spec validation for the INT-US-24 e2e proof.\n"
        'version: "1.0"\n'
        "steps:\n"
        "  - name: s01_one_sentence\n    rule: S01\n"
        "  - name: s02_single_setup\n    rule: S02\n"
        "  - name: s06_concrete_example\n    rule: S06\n"
        "  - name: s09_error_path\n    rule: S09\n"
        "  - name: s10_done_definition\n    rule: S10\n"
        "  - name: s08_ambiguity\n    rule: S08\n",
        encoding="utf-8",
    )
    spec = project_dir / "specs" / "greet_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC_BODY, encoding="utf-8")
    return project_dir


@contextlib.contextmanager
def _scenario_world(adapter: ScenarioWorldAdapter, implementer: ImplementerState, record: list):
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch(
                "specweaver.infrastructure.llm.factory.create_llm_adapter",
                return_value=(_settings_mock(), adapter, MagicMock()),
            )
        )
        # The router would otherwise build a REAL provider adapter from the
        # registry (bypassing the factory patch); None → handlers fall back to
        # context.llm, i.e. the scripted adapter.
        stack.enter_context(
            patch(
                "specweaver.infrastructure.llm.router.ModelRouter.get_for_task",
                return_value=None,
            )
        )
        stack.enter_context(
            patch(
                "specweaver.core.flow.handlers.generation.GenerateCodeHandler.execute",
                new=_make_implementer(implementer),
            )
        )
        for target in (
            "specweaver.core.flow.handlers.generation.GenerateTestsHandler.execute",
            "specweaver.core.flow.handlers.validation.ValidateCodeHandler.execute",
        ):
            stack.enter_context(patch(target, new=_ok_execute))
        for target in (
            "specweaver.core.flow.handlers.review.ReviewSpecHandler.execute",
            "specweaver.core.flow.handlers.review.ReviewCodeHandler.execute",
        ):
            stack.enter_context(patch(target, new=_accepted_execute))
        stack.enter_context(
            patch(
                "specweaver.core.flow.handlers.validation.ValidateTestsHandler.execute",
                new=_make_validate_tests_wrapper(record),
            )
        )
        yield


def _snapshot(project: Path) -> set[str]:
    """Relative file inventory, ignoring caches (pytest/pycache) and engine-
    internal state under .specweaver (topology cache etc.) — those are tooling
    noise, not verification artifacts."""
    ignored = ("__pycache__", ".pytest_cache", ".specweaver")
    return {
        str(p.relative_to(project)).replace("\\", "/")
        for p in project.rglob("*")
        if p.is_file() and not any(part in ignored for part in p.parts)
    }


EXPECTED_ARTIFACTS = {
    "contracts/greet_contract.py",
    "scenarios/definitions/greet_scenarios.yaml",
    "scenarios/generated/test_greet_scenarios.py",
    "src/greet.py",
}


def _latest_run(data_dir, project_name: str):
    """The persisted run record — where step error messages actually live
    (the rich CLI display does not surface them on these paths)."""
    from specweaver.core.flow.engine.store import StateStore

    return StateStore(data_dir / "pipeline_state.db").get_latest_run(
        project_name, "scenario_integration"
    )


def _run_cli(project: Path):
    return runner.invoke(
        app,
        [
            "run",
            "scenario_integration",
            str(project / "specs" / "greet_spec.md"),
            "--project",
            str(project),
        ],
    )


# --------------------------------------------------------------------------- #
# E1 — the US-24 sentence, happy                                              #
# --------------------------------------------------------------------------- #


def test_e1_happy_completes_with_zero_arbitration_cost(tmp_path: Path) -> None:
    project = _init_project(tmp_path, "us24_e1")
    adapter = ScenarioWorldAdapter([GOOD_SET], verdicts=[])
    implementer = ImplementerState([CORRECT_IMPL])
    record: list = []
    before = _snapshot(project)

    with _scenario_world(adapter, implementer, record):
        result = _run_cli(project)

    assert result.exit_code == 0, result.output
    # Behavioral verification genuinely EXECUTED tests (A4 + anti-false-green):
    assert record and record[0].output["total"] == 3 and record[0].output["passed"] == 3
    # Green round costs zero arbitration LLM calls (NFR-2).
    assert adapter.arb_calls == 0
    # A4 artifact inventory: exactly the expected droppings, no strays.
    assert _snapshot(project) - before == EXPECTED_ARTIFACTS


# --------------------------------------------------------------------------- #
# E2 — code_bug: unit-green but business-wrong, caught and fixed               #
# --------------------------------------------------------------------------- #


def test_e2_code_bug_loop_buggy_then_fixed(tmp_path: Path) -> None:
    project = _init_project(tmp_path, "us24_e2")
    adapter = ScenarioWorldAdapter([GOOD_SET], verdicts=[CODE_BUG_VERDICT])
    implementer = ImplementerState([WRONG_IMPL, CORRECT_IMPL])
    record: list = []

    with _scenario_world(adapter, implementer, record):
        result = _run_cli(project)

    assert result.exit_code == 0, result.output
    assert adapter.arb_calls == 1
    # Round 1 genuinely failed on real pytest; round 2 genuinely passed.
    assert record[0].status == StepStatus.FAILED and record[0].output["failed"] == 2
    assert record[1].status == StepStatus.PASSED and record[1].output["passed"] == 3
    # The implementer received the arbiter's verdict on round 2 — vocabulary-free.
    round2_feedback = implementer.received_feedback[1]
    assert round2_feedback is not None
    message = round2_feedback["findings"]["results"][0]["message"].lower()
    from specweaver.core.flow.handlers.arbiter import SCENARIO_VOCABULARY

    for banned in SCENARIO_VOCABULARY:
        assert banned.lower() not in message


# --------------------------------------------------------------------------- #
# E3 — scenario_error: regeneration WITH the prior-verdict block               #
# --------------------------------------------------------------------------- #


def test_e3_scenario_error_regenerates_with_delta(tmp_path: Path) -> None:
    project = _init_project(tmp_path, "us24_e3")
    adapter = ScenarioWorldAdapter(
        [BAD_EXPECTATION_SET, GOOD_SET], verdicts=[SCENARIO_ERROR_VERDICT]
    )
    implementer = ImplementerState([CORRECT_IMPL])
    record: list = []

    with _scenario_world(adapter, implementer, record):
        result = _run_cli(project)

    assert result.exit_code == 0, result.output
    assert adapter.scen_calls == 2
    # FR-4 end-to-end: the second generation prompt carries the arbiter's delta.
    assert "Prior Verdict Feedback" in adapter.scen_prompts[1]
    assert "not 'Hi <name>'" in adapter.scen_prompts[1]


# --------------------------------------------------------------------------- #
# E4 — spec_ambiguity parks (exit 0, resume hint, PARKED row)                  #
# --------------------------------------------------------------------------- #


def test_e4_spec_ambiguity_parks(tmp_path: Path, monkeypatch, _isolated_env) -> None:
    project = _init_project(tmp_path, "us24_e4")
    monkeypatch.setenv("SW_PROJECT", str(project))
    adapter = ScenarioWorldAdapter([GOOD_SET], verdicts=[AMBIGUITY_VERDICT])
    implementer = ImplementerState([WRONG_IMPL])
    record: list = []

    with _scenario_world(adapter, implementer, record):
        result = _run_cli(project)

    assert result.exit_code == 0, result.output  # parked is NOT an error (NFR-5/6 parity)
    assert "resume" in result.output.lower()
    from specweaver.core.flow.engine.state import RunStatus

    run_state = _latest_run(_isolated_env, "us24_e4")
    assert run_state is not None and run_state.status == RunStatus.PARKED


# --------------------------------------------------------------------------- #
# E5 — retries exhausted: bounded, loud                                        #
# --------------------------------------------------------------------------- #


def test_e5_retries_exhausted_fails_loud(tmp_path: Path, _isolated_env) -> None:
    project = _init_project(tmp_path, "us24_e5")
    adapter = ScenarioWorldAdapter([GOOD_SET], verdicts=[CODE_BUG_VERDICT] * 4)
    implementer = ImplementerState([WRONG_IMPL])  # never fixed
    record: list = []

    with _scenario_world(adapter, implementer, record):
        result = _run_cli(project)

    assert result.exit_code != 0
    assert adapter.arb_calls == 4  # initial + max_retries(3)
    # The arbiter's actionable message is persisted on the failed run record
    # (the rich CLI table does not render step error messages on this path).
    run_state = _latest_run(_isolated_env, "us24_e5")
    assert run_state is not None and "salutation" in run_state.model_dump_json()


# --------------------------------------------------------------------------- #
# E6 — zero-collected: the false-green guard chain, end to end                 #
# --------------------------------------------------------------------------- #


def test_e6_zero_collected_fails_loud(tmp_path: Path) -> None:
    project = _init_project(tmp_path, "us24_e6")
    adapter = ScenarioWorldAdapter([EMPTY_SET], verdicts=[])
    implementer = ImplementerState([CORRECT_IMPL])
    record: list = []

    with _scenario_world(adapter, implementer, record):
        result = _run_cli(project)

    assert result.exit_code != 0
    assert "no scenario tests" in result.output.lower()
    assert adapter.arb_calls == 0  # zero-total short-circuits without LLM spend


# --------------------------------------------------------------------------- #
# E7 — park -> resume: honest loud failure (evidence is not persisted)         #
# --------------------------------------------------------------------------- #


def test_e7_resume_after_park_heals_through_the_loop(
    tmp_path: Path, monkeypatch, _isolated_env
) -> None:
    """Cross-session truth (R/B RED-1 + inherited defect #10): feedback is NOT
    persisted, so the resumed arbiter re-executes with the evidence absent and
    fails honest-and-loud (message pinned at the unit tier) — which trips the
    loop_back and RE-RUNS the whole verification round: dual fan-out, fresh
    implementation, real pytest, fresh evidence. The park heals through the
    loop, not through fake persistence. (Required fixing defect #10: `sw
    resume` never wired context.llm, silently ERRORing every resumed LLM
    step.)"""
    project = _init_project(tmp_path, "us24_e7")
    monkeypatch.setenv("SW_PROJECT", str(project))
    adapter = ScenarioWorldAdapter([GOOD_SET], verdicts=[AMBIGUITY_VERDICT])
    # Session 1 implements WRONG (tests fail -> ambiguity park); the resume
    # round implements CORRECT -> green -> arbiter short-circuits, no LLM.
    implementer = ImplementerState([WRONG_IMPL, CORRECT_IMPL])
    record: list = []

    with _scenario_world(adapter, implementer, record):
        # Session 1: ambiguity park.
        result1 = _run_cli(project)
        assert result1.exit_code == 0, result1.output

        # Session 2: resume — fresh RunContext, absent evidence -> honest
        # arbiter ERROR -> loop_back -> full fresh verification round.
        result2 = CliRunner().invoke(app, ["resume"])

    assert result2.exit_code == 0, result2.output
    from specweaver.core.flow.engine.state import RunStatus

    run_state = _latest_run(_isolated_env, "us24_e7")
    assert run_state is not None and run_state.status == RunStatus.COMPLETED
    # Only session 1 arbitrated via LLM; the healed round short-circuited green.
    assert adapter.arb_calls == 1
    # The loop round regenerated scenarios (evidence re-published naturally).
    assert adapter.scen_calls == 2
    # Round 1 failed on real pytest, the healed round genuinely passed.
    assert record[0].output["failed"] == 2
    assert record[-1].output["passed"] == 3


def test_e7b_resume_without_llm_warns_and_degrades_gracefully(
    tmp_path: Path, monkeypatch, _isolated_env
) -> None:
    # [Graceful degradation] G-c: defect #10's guarded branch — if the adapter
    # cannot be built at resume time, resume WARNS and proceeds with llm=None
    # (LLM steps fail loud downstream; never a crash).
    from specweaver.infrastructure.llm.factory import LLMAdapterError

    project = _init_project(tmp_path, "us24_e7b")
    monkeypatch.setenv("SW_PROJECT", str(project))
    adapter = ScenarioWorldAdapter([GOOD_SET], verdicts=[AMBIGUITY_VERDICT])
    implementer = ImplementerState([WRONG_IMPL])
    record: list = []

    with _scenario_world(adapter, implementer, record):
        result1 = _run_cli(project)
        assert result1.exit_code == 0, result1.output

        with patch(
            "specweaver.infrastructure.llm.factory.create_llm_adapter",
            side_effect=LLMAdapterError("no provider configured"),
        ):
            result2 = CliRunner().invoke(app, ["resume"])

    assert result2.exit_code != 0  # degraded, loud — never green, never a crash
    assert "No LLM configured" in result2.output


# --------------------------------------------------------------------------- #
# E8 — scenario-generation retry exhaustion: loud pipeline failure             #
# --------------------------------------------------------------------------- #


def test_e8_generator_exhaustion_fails_loud(tmp_path: Path, _isolated_env) -> None:
    project = _init_project(tmp_path, "us24_e8")
    adapter = ScenarioWorldAdapter(["this is not json at all"], verdicts=[])
    implementer = ImplementerState([CORRECT_IMPL])
    record: list = []

    with _scenario_world(adapter, implementer, record):
        result = _run_cli(project)

    assert result.exit_code != 0
    assert adapter.scen_calls == 3  # ScenarioGenerator max_retries
    assert "Pipeline failed" in result.output
    # The dual step's actionable message is persisted on the run record.
    run_state = _latest_run(_isolated_env, "us24_e8")
    assert run_state is not None and "Scenario pipeline failed" in run_state.model_dump_json()
