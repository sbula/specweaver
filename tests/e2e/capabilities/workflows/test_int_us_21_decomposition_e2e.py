# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-21 Verifiable Proof (FR-10): the feature-decomposition journey, end to end.

The **first test in the suite to drive a bundled pipeline THROUGH a HITL gate.** `INT-US-02`'s
E6/E7 claimed to and did not: PARKED and COMPLETED both exit 0, so their exit-code assertions could
not tell the two apart, and the scripted verdicts were never consumed.

Real surfaces throughout `sw run feature_decomposition`: the real CLI, the real registry, the real
`validation_spec_feature` battery, the real `DecomposeFeatureHandler`, real artifact and stub
writes, real approve-on-resume, real SQLite state across three separate `CliRunner` sessions. The
scripted edge is the LLM only.

> **Every assertion reads the PERSISTED run status, never the exit code.** `cli.py` maps
> COMPLETED → 0, FAILED → 1 and **PARKED → 0** ("not an error, just parked"). An exit-code
> assertion cannot distinguish a parked journey from a finished one — which is exactly how
> INT-US-02's proof came to be vacuous.

The journey has two HITL gates, so the happy path is three sessions:

    session 1  draft_feature (spec pre-exists -> exists-skip) -> PARK #1
    session 2  resume = approval -> validate_feature -> decompose -> PARK #2
    session 3  resume = approval -> COMPLETED
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

pytestmark = pytest.mark.e2e

PIPELINE = "feature_decomposition"
FEATURE = "onboarding"
SPEC_NAME = f"{FEATURE}_feature_spec.md"


# --------------------------------------------------------------------------- #
# Fixtures                                                                      #
# --------------------------------------------------------------------------- #

#: Measured against the real `validation_spec_feature` battery during SF-03 Phase 0:
#: 8 pass / 3 warn / 0 fail. `ValidateSpecHandler` counts only FAIL toward the gate
#: (`validation.py`: `all_passed = len([r for r in results if r.status is FAIL]) == 0`), so this
#: clears it. The three warnings are left alone on purpose — chasing S07 by bolting on a Scenarios
#: section would make the fixture unrepresentative of what a user actually hands to this pipeline.
SPEC_BODY = """# Onboarding Feature Spec

## 1. Purpose

The onboarding feature registers a new customer and issues their first invoice.

## 2. Contract

```python
def register(email: str) -> str:
    \"\"\"Register a customer and return the new account id.\"\"\"
```

Example:

```python
register("ada@example.com")  # returns "acct_1"
```

## 3. Error Path

When the email is empty, `register` raises `ValueError` with the message `email required`.

## 4. DAL

DAL_B — the feature writes to the customer store but performs no untrusted execution.

## Done Definition

- [ ] `register` returns a new account id for a valid email (FR-1)
- [ ] `register` raises `ValueError` for an empty email (FR-2)
"""


def _plan_json(components: list[str] | None = None, coverage: float = 1.0) -> str:
    """A DecompositionPlan payload as the LLM would return it."""
    names = ["auth", "billing"] if components is None else components
    return json.dumps(
        {
            "feature_spec": f"specs/{SPEC_NAME}",
            "components": [
                {
                    "component": name,
                    "exists": False,
                    "change_nature": "new_interface",
                    "description": f"{name} handles its slice of onboarding.",
                    "proposed_dal": "DAL_B",
                    "dependencies": [],
                    "target_modules": [f"src/{name}"],
                    "confidence": 85,
                }
                for name in names
            ],
            "integration_seams": [],
            "build_sequence": names,
            "coverage_score": coverage,
            "alignment_notes": [],
            "timestamp": "2026-07-28T00:00:00Z",
        }
    )


class ScriptedLLM:
    """Returns queued payloads. Counts calls so NFR-3 (LLM economy) is assertable."""

    def __init__(self, payloads: list[str]) -> None:
        self._payloads = list(payloads)
        self.calls = 0

    async def generate(self, messages, config=None, *args, **kwargs) -> LLMResponse:
        idx = min(self.calls, len(self._payloads) - 1)
        self.calls += 1
        return LLMResponse(text=self._payloads[idx], model="scripted-1")

    async def generate_with_tools(self, messages, config, dispatcher, **kwargs) -> LLMResponse:
        return await self.generate(messages, config)


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / ".specweaver-test"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(d))
    return d


def _settings_mock():
    from specweaver.core.config.settings import SandboxSettings

    settings = MagicMock()
    settings.llm.model = "scripted-1"
    settings.llm.temperature = 0.2
    settings.llm.max_output_tokens = 4096
    settings.sandbox = SandboxSettings()
    return settings


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """An initialised project whose feature spec already exists (AD-5 spec-pre-exists posture)."""
    project_dir = tmp_path / FEATURE
    project_dir.mkdir()
    result = runner.invoke(app, ["init", FEATURE, "--path", str(project_dir)])
    assert result.exit_code == 0, result.output

    specs = project_dir / "specs"
    specs.mkdir(exist_ok=True)
    (specs / SPEC_NAME).write_text(SPEC_BODY, encoding="utf-8")
    return project_dir


@contextlib.contextmanager
def scripted_world(llm: ScriptedLLM):
    """Only the LLM is doubled. Everything downstream of it is the real thing."""
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch(
                "specweaver.infrastructure.llm.factory.create_llm_adapter",
                return_value=(_settings_mock(), llm, MagicMock()),
            )
        )
        # Without this the router builds a REAL provider adapter from the registry, bypassing the
        # factory patch entirely — a live API call inside a "mocked" test (vacuous-proof pattern 5,
        # found for real in INT-US-02's e2e). None makes handlers fall back to context.llm.
        stack.enter_context(
            patch(
                "specweaver.infrastructure.llm.router.ModelRouter.get_for_task",
                return_value=None,
            )
        )
        yield


# --------------------------------------------------------------------------- #
# Session helpers — a fresh CliRunner per session, as a real user would         #
# --------------------------------------------------------------------------- #


def _start(project: Path, spec: str = SPEC_NAME):
    return runner.invoke(
        app, ["run", PIPELINE, str(project / "specs" / spec), "--project", str(project)]
    )


def _resume(project: Path, run_id: str):
    return runner.invoke(
        app, ["run", PIPELINE, str(project / "specs" / SPEC_NAME), "--project", str(project),
              "--resume", run_id]
    )


def _store(data_dir: Path):
    from specweaver.core.flow.engine.store import StateStore

    return StateStore(data_dir / "pipeline_state.db")


def _latest(data_dir: Path):
    """The persisted run — the only honest source of terminal status (see module docstring)."""
    return _store(data_dir).get_latest_run(FEATURE, PIPELINE)


def _artifact(project: Path) -> Path:
    return project / "specs" / f"{FEATURE}_feature_spec_decomposition.yaml"


def _stub(project: Path, component: str) -> Path:
    return project / "specs" / f"{component}_spec.md"


# --------------------------------------------------------------------------- #
# E1 — the happy three-session journey                                          #
# --------------------------------------------------------------------------- #


class TestE1HappyJourney:
    """`sw run feature_decomposition` -> park -> resume -> park -> resume -> COMPLETED."""

    def test_the_journey_completes_across_three_sessions(
        self, project: Path, data_dir: Path
    ) -> None:
        from specweaver.core.flow.engine.state import RunStatus

        llm = ScriptedLLM([_plan_json()])
        with scripted_world(llm):
            first = _start(project)
            assert first.exit_code == 0, first.output

            run = _latest(data_dir)
            assert run is not None, "no run was persisted"
            assert run.status == RunStatus.PARKED, "session 1 should park at the draft gate"

            _resume(project, run.run_id)
            mid = _store(data_dir).load_run(run.run_id)
            assert mid.status == RunStatus.PARKED, "session 2 should park at the review gate"

            _resume(project, run.run_id)
            final = _store(data_dir).load_run(run.run_id)

        assert final.status == RunStatus.COMPLETED, (
            f"journey did not finish: {final.status}, step {final.current_step}"
        )

    def test_the_decomposition_costs_exactly_one_llm_call(
        self, project: Path, data_dir: Path
    ) -> None:
        """NFR-3: persistence, hydration, approval and stubs add ZERO LLM calls."""
        llm = ScriptedLLM([_plan_json()])
        with scripted_world(llm):
            _start(project)
            run_id = _latest(data_dir).run_id
            _resume(project, run_id)
            _resume(project, run_id)

        assert llm.calls == 1, f"expected one decompose call, got {llm.calls}"

    def test_the_artifact_and_stubs_reach_disk(self, project: Path, data_dir: Path) -> None:
        llm = ScriptedLLM([_plan_json()])
        with scripted_world(llm):
            _start(project)
            run_id = _latest(data_dir).run_id
            _resume(project, run_id)
            _resume(project, run_id)

        assert _artifact(project).is_file(), "no decomposition artifact"
        assert _stub(project, "auth").is_file()
        assert _stub(project, "billing").is_file()
        assert "{{" not in _stub(project, "auth").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# E2-E11                                                                        #
# --------------------------------------------------------------------------- #


def _reach_decompose(project: Path, data_dir: Path) -> str:
    """Drive sessions 1-2 so the run is parked at the review gate. Returns the run id."""
    _start(project)
    run_id = _latest(data_dir).run_id
    _resume(project, run_id)
    return run_id


class TestE2CoverageBelowThreshold:
    """A plan the decomposer is not confident about must stop the journey, loudly."""

    def test_low_coverage_fails_the_run_and_writes_no_artifact(
        self, project: Path, data_dir: Path
    ) -> None:
        from specweaver.core.flow.engine.state import RunStatus

        with scripted_world(ScriptedLLM([_plan_json(coverage=0.5)])):
            run_id = _reach_decompose(project, data_dir)
            run = _store(data_dir).load_run(run_id)

        # PARKED, not FAILED: `gates.py` parks a HITL gate unconditionally, so a failed
        # decompose still stops at the review gate for a human. That is exactly FR-10's
        # "coverage<1.0 -> HITL park with the failure surfaced -> resume re-executes decompose".
        # The AD-2 flavour is a *failed* gate-park: record WAITING_FOR_INPUT + stored result
        # FAILED, which is deliberately NOT approvable, so a resume re-runs the step.
        assert run.status == RunStatus.PARKED
        assert not _artifact(project).exists()

    def test_the_coverage_reason_is_persisted_for_the_human(
        self, project: Path, data_dir: Path
    ) -> None:
        """The rich display does not surface step errors on this path; the record must."""
        with scripted_world(ScriptedLLM([_plan_json(coverage=0.5)])):
            run_id = _reach_decompose(project, data_dir)
            run = _store(data_dir).load_run(run_id)

        messages = " ".join((r.result.error_message or "") for r in run.step_records if r.result)
        assert "overage" in messages, messages


class TestE3MalformedLlmOutput:
    def test_garbage_json_fails_loudly_and_writes_no_artifact(
        self, project: Path, data_dir: Path
    ) -> None:
        from specweaver.core.flow.engine.state import RunStatus

        with scripted_world(ScriptedLLM(["not json at all {{{"])):
            run_id = _reach_decompose(project, data_dir)
            run = _store(data_dir).load_run(run_id)

        # Parks for the same reason as E2 — the HITL gate fires whatever the step returned.
        assert run.status == RunStatus.PARKED
        assert not _artifact(project).exists()

    def test_the_parse_failure_names_the_schema(self, project: Path, data_dir: Path) -> None:
        with scripted_world(ScriptedLLM(["not json at all {{{"])):
            run_id = _reach_decompose(project, data_dir)
            run = _store(data_dir).load_run(run_id)

        messages = " ".join((r.result.error_message or "") for r in run.step_records if r.result)
        assert "DecompositionPlan" in messages, messages


class TestE4MissingSpec:
    def test_a_missing_spec_does_not_crash_the_cli(self, project: Path, data_dir: Path) -> None:
        (project / "specs" / SPEC_NAME).unlink()

        with scripted_world(ScriptedLLM([_plan_json()])):
            result = _start(project)

        assert "Traceback" not in result.output, result.output


class TestE5CrossSessionRehydration:
    """The decomposition must survive a process boundary, not just a park."""

    def test_the_hydrated_plan_matches_the_artifact_after_a_resume(
        self, project: Path, data_dir: Path
    ) -> None:
        from ruamel.yaml import YAML

        with scripted_world(ScriptedLLM([_plan_json()])):
            run_id = _reach_decompose(project, data_dir)
            _resume(project, run_id)
            run = _store(data_dir).load_run(run_id)

        decompose_record = next(r for r in run.step_records if r.step_name == "decompose")
        persisted = decompose_record.result.output["plan"]
        on_disk = YAML(typ="safe").load(_artifact(project).read_text(encoding="utf-8"))

        assert persisted == on_disk


class TestE6ZeroComponents:
    def test_an_empty_plan_still_completes_and_writes_an_artifact(
        self, project: Path, data_dir: Path
    ) -> None:
        from specweaver.core.flow.engine.state import RunStatus

        with scripted_world(ScriptedLLM([_plan_json(components=[])])):
            run_id = _reach_decompose(project, data_dir)
            _resume(project, run_id)
            run = _store(data_dir).load_run(run_id)

        assert run.status == RunStatus.COMPLETED
        assert _artifact(project).is_file()
        written = {p.name for p in (project / "specs").glob("*_spec.md")}
        assert written == {SPEC_NAME}, written


class TestE7StubNoOverwrite:
    def test_a_hand_authored_component_spec_is_untouched(
        self, project: Path, data_dir: Path
    ) -> None:
        mine = _stub(project, "auth")
        mine.write_text("# auth - hand written, do not clobber\n", encoding="utf-8")
        before = mine.read_bytes()

        with scripted_world(ScriptedLLM([_plan_json()])):
            run_id = _reach_decompose(project, data_dir)
            _resume(project, run_id)

        assert mine.read_bytes() == before
        assert _stub(project, "billing").is_file(), "the other component was still created"


class TestE9FeatureSpecNameCollision:
    """R-10 through the real CLI: a component that would target the feature spec."""

    def test_the_feature_spec_survives_and_the_journey_completes(
        self, project: Path, data_dir: Path
    ) -> None:
        from specweaver.core.flow.engine.state import RunStatus

        before = (project / "specs" / SPEC_NAME).read_bytes()
        colliding = [f"{FEATURE}_feature", "auth"]

        with scripted_world(ScriptedLLM([_plan_json(components=colliding)])):
            run_id = _reach_decompose(project, data_dir)
            _resume(project, run_id)
            run = _store(data_dir).load_run(run_id)

        assert run.status == RunStatus.COMPLETED
        assert (project / "specs" / SPEC_NAME).read_bytes() == before
        record = next(r for r in run.step_records if r.step_name == "decompose")
        assert record.result.output["component_specs"]["collided"] == [f"{FEATURE}_feature"]


class TestE10JourneyIsRerunnable:
    """Running the whole journey twice on one spec must be safe and idempotent."""

    def test_a_second_journey_reuses_the_artifact_identity_and_skips_stubs(
        self, project: Path, data_dir: Path
    ) -> None:
        from specweaver.core.flow.engine.state import RunStatus
        from specweaver.infrastructure.llm.lineage import extract_artifact_uuid

        with scripted_world(ScriptedLLM([_plan_json()])):
            run_id = _reach_decompose(project, data_dir)
            _resume(project, run_id)
        first_uuid = extract_artifact_uuid(_artifact(project).read_text(encoding="utf-8"))

        with scripted_world(ScriptedLLM([_plan_json()])):
            second_id = _reach_decompose(project, data_dir)
            _resume(project, second_id)
            second_run = _store(data_dir).load_run(second_id)

        assert second_id != run_id, "the second journey should be its own run"
        assert second_run.status == RunStatus.COMPLETED
        assert extract_artifact_uuid(_artifact(project).read_text(encoding="utf-8")) == first_uuid
        record = next(r for r in second_run.step_records if r.step_name == "decompose")
        assert sorted(record.result.output["component_specs"]["skipped"]) == ["auth", "billing"]


class TestE11ResumeAnUnparkedRun:
    """Resuming a finished run used to leave it stuck in RUNNING.

    `PipelineRunner.resume()` sets RunStatus.RUNNING unconditionally; with every step already done
    the loop had nothing to execute, and the `finally:` block persisted the corrupted status. A
    completed journey then reported as in-flight forever.

    The knowledge already existed in the wrong place: the `sw resume` command's auto-discovery only
    offers runs in (PARKED, FAILED), but `sw run --resume <id>` bypasses that filter and reached
    the engine, which had no guard at all.
    """

    def test_resuming_a_finished_run_is_refused(self, project: Path, data_dir: Path) -> None:
        from specweaver.core.flow.engine.state import RunStatus

        with scripted_world(ScriptedLLM([_plan_json()])):
            run_id = _reach_decompose(project, data_dir)
            _resume(project, run_id)
            assert _store(data_dir).load_run(run_id).status == RunStatus.COMPLETED

        second_llm = ScriptedLLM([_plan_json()])
        with scripted_world(second_llm):
            result = _resume(project, run_id)
            after = _store(data_dir).load_run(run_id)

        assert result.exit_code == 1, result.output
        assert "already completed" in result.output
        assert after.status == RunStatus.COMPLETED, "the finished run was reopened"
        assert second_llm.calls == 0, "a refused resume must not re-run the decomposition"

    def test_a_parked_run_is_still_resumable(self, project: Path, data_dir: Path) -> None:
        """The guard must refuse ONLY finished runs — the whole journey depends on resuming parks."""
        from specweaver.core.flow.engine.state import RunStatus

        with scripted_world(ScriptedLLM([_plan_json()])):
            run_id = _reach_decompose(project, data_dir)
            assert _store(data_dir).load_run(run_id).status == RunStatus.PARKED

            result = _resume(project, run_id)

        assert result.exit_code == 0, result.output
        assert _store(data_dir).load_run(run_id).status == RunStatus.COMPLETED


class TestE8ValidationFailureLoopsBack:
    """The `validate_feature` -> `loop_back` -> `draft_feature` arm, previously unexercised.

    `feature_decomposition.yaml` gives validate_feature `on_fail: loop_back`,
    `loop_target: draft_feature`, `max_retries: 3`. Nothing in the suite had ever driven a spec
    that FAILS the battery, so the entire arm — and its 3-strike bound — was untested. SF-02's
    coverage tests exercise a different gate on a different step.

    Asserted at the level that matters to a user rather than by pinning the exact loop mechanics:
    a spec that fails validation must never yield a decomposition, and the journey must stop
    rather than spin.
    """

    #: Measured against the real battery: 4 FAILs (S06, S07, S09, S10).
    BAD_SPEC = "# Thin Feature Spec\n\n## 1. Purpose\n\nDoes a thing.\n"

    def test_a_failing_spec_never_produces_a_decomposition(
        self, project: Path, data_dir: Path
    ) -> None:
        from specweaver.core.flow.engine.state import RunStatus

        (project / "specs" / SPEC_NAME).write_text(self.BAD_SPEC, encoding="utf-8")
        llm = ScriptedLLM([_plan_json()])

        with scripted_world(llm):
            _start(project)
            run_id = _latest(data_dir).run_id
            # Far more resumes than the 3-strike budget allows.
            for _ in range(6):
                _resume(project, run_id)
            run = _store(data_dir).load_run(run_id)

        assert not _artifact(project).exists(), "a spec that fails validation was decomposed"
        assert llm.calls == 0, "the decomposer ran despite validation failing"
        assert run.status != RunStatus.COMPLETED, "the journey completed on a failing spec"

    def test_the_journey_parks_rather_than_spinning_or_completing(
        self, project: Path, data_dir: Path
    ) -> None:
        """Measured behaviour of the loop-back arm, pinned so a change is visible.

        Each resume approves the draft gate, validate_feature FAILS, the gate loops back to
        draft_feature, and the run parks at step 0 again. It is therefore stable-but-unbounded:
        the user can resume forever and always lands back at the draft gate.

        NFR-2 already records why the 3-strike budget never bites here — `_execute_loop`
        re-initialises `attempts` on every entry, so each session gets a fresh budget. INT-US-21
        deliberately does not fix that (persisting attempt counters is a state-schema change,
        `C-FLOW-07` territory). This asserts the shape so the delegation stays honest.
        """
        from specweaver.core.flow.engine.state import RunStatus

        (project / "specs" / SPEC_NAME).write_text(self.BAD_SPEC, encoding="utf-8")

        with scripted_world(ScriptedLLM([_plan_json()])):
            _start(project)
            run_id = _latest(data_dir).run_id
            for _ in range(3):
                _resume(project, run_id)
            run = _store(data_dir).load_run(run_id)

        assert run.status == RunStatus.PARKED
        assert run.current_step == 0, "the loop_back should return to draft_feature"
        assert run.step_records[0].attempt <= 3

    def test_the_validation_failure_is_recorded_for_the_human(
        self, project: Path, data_dir: Path
    ) -> None:
        (project / "specs" / SPEC_NAME).write_text(self.BAD_SPEC, encoding="utf-8")

        with scripted_world(ScriptedLLM([_plan_json()])):
            _start(project)
            run_id = _latest(data_dir).run_id
            _resume(project, run_id)
            run = _store(data_dir).load_run(run_id)

        # Was a strict xfail until TECH-021 was fixed (2026-07-28): `loop_back` discarded the
        # failing step's result, leaving status=running / result=None. The marker was the
        # tripwire -- it XPASSed the moment `gates.py` started retaining the result, which is
        # what signalled the marker could go.
        validate = next(r for r in run.step_records if r.step_name == "validate_feature")
        assert validate.result is not None, (
            "the failing validation result was discarded by loop_back"
        )
        rules = validate.result.output.get("results", [])
        failed = [r["rule_id"] for r in rules if str(r["status"]).lower() == "fail"]
        assert failed, f"validation passed a spec measured to fail: {rules}"


# --------------------------------------------------------------------------- #
# CB-4 — teardown and interrupt survival (E12-E14)                              #
# --------------------------------------------------------------------------- #


class _InterruptingDecompose:
    """Stands in for a user pressing Ctrl-C while the decomposer is working."""

    async def execute(self, step, context):
        raise KeyboardInterrupt


class TestE12InterruptSurvival:
    """What survives a Ctrl-C, and what a user can do next.

    Scope stated honestly, because a probe corrected the first version of this docstring:
    disabling BOTH `_save_handover` and `_flush_telemetry` in the runner's `finally:` leaves every
    test in this class green. The run survives because the store persists after each step, not
    because of the teardown block — so these tests prove **resumability**, and say nothing about
    whether handover context or telemetry actually flush. That remains unproven, which is what
    `TECH-017` already records about graceful shutdown repo-wide.

    What IS proven: the interrupted run is persisted, loadable, structurally intact, resumable to
    completion, and leaves no half-written artifact — and the message names an id that really loads.

    Written in-process rather than by delivering a real SIGINT. Python surfaces SIGINT AS
    `KeyboardInterrupt`, so this exercises the same handler chain, the same `finally:`, and the
    same CLI branch — on every platform. The one thing it does not cover is OS-level signal
    delivery. That distinction is stated rather than hidden behind a blanket
    `pytest.skip("...Windows...")`, which is why the repo's only other SIGINT test has never run
    here.
    """

    def test_the_run_survives_the_interrupt_and_is_resumable(
        self, project: Path, data_dir: Path
    ) -> None:
        from specweaver.core.flow.engine.state import RunStatus

        with scripted_world(ScriptedLLM([_plan_json()])):
            _start(project)
            run_id = _latest(data_dir).run_id

            with patch(
                "specweaver.core.flow.handlers.decompose.DecomposeFeatureHandler.execute",
                new=_InterruptingDecompose.execute,
            ):
                interrupted = _resume(project, run_id)

            assert interrupted.exit_code == 130, interrupted.output

            after_interrupt = _store(data_dir).load_run(run_id)
            assert after_interrupt is not None, "the interrupted run was not persisted at all"

            # The real point: the journey can still be finished afterwards. It costs one extra
            # cycle, correctly — the interrupted decompose never reached its review gate, so
            # resuming re-runs it and THEN parks for the approval the human never gave.
            _resume(project, run_id)
            assert _store(data_dir).load_run(run_id).status == RunStatus.PARKED

            _resume(project, run_id)
            final = _store(data_dir).load_run(run_id)

        assert final.status == RunStatus.COMPLETED
        assert _artifact(project).is_file()

    def test_the_interrupt_names_a_run_the_user_can_actually_resume(
        self, project: Path, data_dir: Path
    ) -> None:
        """E13 — the hint is only useful if the id it prints really loads."""
        import re

        with scripted_world(ScriptedLLM([_plan_json()])):
            _start(project)
            run_id = _latest(data_dir).run_id

            with patch(
                "specweaver.core.flow.handlers.decompose.DecomposeFeatureHandler.execute",
                new=_InterruptingDecompose.execute,
            ):
                result = _resume(project, run_id)

        flattened = re.sub(r"\s+", " ", result.output)
        match = re.search(r"--resume ([0-9a-f-]{36})", flattened)

        assert match, f"no resumable run id in the interrupt message: {flattened}"
        assert _store(data_dir).load_run(match.group(1)) is not None, (
            "the printed id does not load"
        )

    def test_no_half_written_artifact_survives_the_interrupt(
        self, project: Path, data_dir: Path
    ) -> None:
        """E14 — the decomposition is either absent or complete, never truncated."""
        from ruamel.yaml import YAML

        with scripted_world(ScriptedLLM([_plan_json()])):
            _start(project)
            run_id = _latest(data_dir).run_id

            with patch(
                "specweaver.core.flow.handlers.decompose.DecomposeFeatureHandler.execute",
                new=_InterruptingDecompose.execute,
            ):
                _resume(project, run_id)

            assert not _artifact(project).exists(), "an artifact appeared for a step that never ran"

            _resume(project, run_id)

        loaded = YAML(typ="safe").load(_artifact(project).read_text(encoding="utf-8"))
        assert [c["component"] for c in loaded["components"]] == ["auth", "billing"]

    def test_the_interrupt_does_not_leave_the_run_unloadable(
        self, project: Path, data_dir: Path
    ) -> None:
        """Handover runs in a `finally:`, so the persisted record must stay readable.

        A run that cannot be deserialised after an interrupt would be worse than one that was
        never saved: the CLI would offer it for resume and then fail on load.
        """
        with scripted_world(ScriptedLLM([_plan_json()])):
            _start(project)
            run_id = _latest(data_dir).run_id

            with patch(
                "specweaver.core.flow.handlers.decompose.DecomposeFeatureHandler.execute",
                new=_InterruptingDecompose.execute,
            ):
                _resume(project, run_id)

            run = _store(data_dir).load_run(run_id)

        assert run is not None
        assert [r.step_name for r in run.step_records] == [
            "draft_feature",
            "validate_feature",
            "decompose",
        ]


class TestTeardownActuallyRuns:
    """The `finally:` teardown claim, which `TestE12InterruptSurvival` does NOT prove.

    Those tests pass with both `_save_handover` and `_flush_telemetry` disabled — the run survives
    because the store persists after each step. So "Run state saved" was an unverified claim about
    a different mechanism. Asserted here by spying on the two calls rather than on their side
    effects, because both are deliberately fail-safe (they swallow their own exceptions and no-op
    without a database), so absence of an effect proves nothing about invocation.
    """

    def _interrupt_and_spy(self, project: Path, data_dir: Path):
        import specweaver.core.flow.engine.handover as handover_mod
        import specweaver.core.flow.engine.runner_utils as runner_utils_mod

        calls = {"handover": 0, "telemetry": 0}
        real_handover = handover_mod.save_handover_context
        real_flush = runner_utils_mod.flush_telemetry

        async def spy_handover(context, run):
            calls["handover"] += 1
            return await real_handover(context, run)

        def spy_flush(*a, **kw):
            calls["telemetry"] += 1
            return real_flush(*a, **kw)

        with scripted_world(ScriptedLLM([_plan_json()])):
            _start(project)
            run_id = _latest(data_dir).run_id

            with patch.object(handover_mod, "save_handover_context", spy_handover), patch.object(
                runner_utils_mod, "flush_telemetry", spy_flush
            ), patch(
                "specweaver.core.flow.handlers.decompose.DecomposeFeatureHandler.execute",
                new=_InterruptingDecompose.execute,
            ):
                _resume(project, run_id)
        return calls

    def test_handover_is_saved_on_the_interrupt_path(
        self, project: Path, data_dir: Path
    ) -> None:
        assert self._interrupt_and_spy(project, data_dir)["handover"] >= 1, (
            "the `finally:` never reached _save_handover, so 'Run state saved' is not true"
        )

    def test_telemetry_is_flushed_on_the_interrupt_path(
        self, project: Path, data_dir: Path
    ) -> None:
        assert self._interrupt_and_spy(project, data_dir)["telemetry"] >= 1, (
            "the `finally:` never reached _flush_telemetry"
        )
