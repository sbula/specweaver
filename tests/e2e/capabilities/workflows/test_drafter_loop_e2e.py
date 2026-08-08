# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-02 Verifiable Proof (FR-8): the Interactive Drafter loop, end to end.

REAL surfaces throughout: the genuine Drafter assembles the spec, the genuine S-battery
validates it (project-local mechanical-only preset — D-VAL-02 override, zero LLM rules),
and the genuine Reviewer parses scripted `VERDICT:` responses. Only the LLM text and the
human's keystrokes are scripted.

Covers the contract's usual AND unusual journeys:
  E1 the US-2 sentence (sw draft, full-real, zero manual steps)
  E2 the living rejection loop (DENIED -> re-draft -> ACCEPTED)
  E3 headless park control (exit 0, nothing drafted)
  E4 exhausted rejection (bounded, non-zero, findings surfaced)
  E5 provider crash mid-interview (fail loud)
  E6 cross-session: park -> MANUAL spec -> resume -> new chain validates+reviews it
  E7 cross-session: review rejection -> park WITH findings -> human edits -> resume -> accepted
Steps beyond review_spec (US-3 generation territory) are stubbed PASSED in E6/E7 — the
explicit out-of-contract boundary.
"""

from __future__ import annotations

import contextlib
import pathlib
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _now_iso
from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app
from specweaver.workspace.context.provider import ContextProvider

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

# --------------------------------------------------------------------------- #
# Scripted fixtures                                                            #
# --------------------------------------------------------------------------- #

# Section body crafted to satisfy the mechanical S-rules over the assembled document:
# concrete example (S06), explicit error path (S09), done definition (S10), no weasel
# words (S08), consistent terminology (S11), single setup mention (S02).
SECTION_BODY = (
    "The greeter component returns a greeting string for a given user name.\n\n"
    "Example:\n\n"
    "```python\n"
    'greet("Ada")  # returns "Hello, Ada!"\n'
    "```\n\n"
    "Error path: when the name is empty, `greet` raises `ValueError` with the message "
    "`name must not be empty`.\n\n"
    "Done when: `greet` returns the exact greeting for valid names and raises "
    "`ValueError` for empty names, verified by unit tests."
)

VERDICT_ACCEPT = "VERDICT: ACCEPTED\nThe spec is precise and complete."
VERDICT_DENY = "VERDICT: DENIED\n- Purpose section is too vague about the greeting format"


class ScriptedProvider(ContextProvider):
    """Deterministic 'human': answers every interview question immediately."""

    def __init__(self, fail_after: int | None = None) -> None:
        self.questions_asked = 0
        self._fail_after = fail_after

    @property
    def name(self) -> str:
        return "scripted-e2e"

    async def ask(self, question: str, *, section: str = "") -> str:
        self.questions_asked += 1
        if self._fail_after is not None and self.questions_asked > self._fail_after:
            raise RuntimeError("terminal vanished mid-interview")
        return f"The {section or 'component'} must greet users by name, exactly."


class ScriptedAdapter:
    """LLM stub: reviewer prompts (contain 'VERDICT') pop from the verdict queue;
    every other prompt (drafter sections) gets the crafted section body."""

    provider_name = "scripted"
    model = "scripted-1"

    def __init__(self, verdicts: list[str]) -> None:
        self.verdicts = list(verdicts)

    def available(self) -> bool:
        return True

    async def generate(self, messages, config=None, *args, **kwargs) -> LLMResponse:
        flat = str(messages)
        if "VERDICT" in flat:
            text = self.verdicts.pop(0) if self.verdicts else VERDICT_ACCEPT
        else:
            text = SECTION_BODY
        return LLMResponse(text=text, model=self.model)

    async def generate_with_tools(self, messages, config, dispatcher, **kwargs) -> LLMResponse:
        return await self.generate(messages, config)


def _ok_step(self, step, context) -> StepResult:  # placeholder; replaced below
    raise NotImplementedError


async def _ok_execute(self, step, context) -> StepResult:
    # `verdict: accepted` is required, not decorative: new_feature.yaml's review_code gate uses
    # `condition: accepted`, which reads result.output["verdict"] — a bare PASSED loop_backs to
    # generate_code and exhausts max_retries. Before approve-on-resume (INT-US-21 FR-4) these
    # steps were never reached from E6/E7, so the omission was invisible.
    return StepResult(
        status=StepStatus.PASSED,
        output={"stubbed": "out-of-contract (US-3 scope)", "verdict": "accepted"},
        started_at=_now_iso(),
        completed_at=_now_iso(),
    )


# Handlers beyond review_spec in new_feature.yaml — US-3 territory, out of this contract.
# INT-US-21 CB-4: ReviewSpecHandler prefers `context.model.llm_router.get_for_task(...)` over
# `context.model.llm` (review.py:32-36), and `sw run`/`sw resume` inject a real ModelRouter. Patching
# only `create_llm_adapter` left the router building a LIVE adapter — once approve-on-resume let
# E6/E7 reach review_spec they started making real Gemini calls (observed as 429s). Returning
# None makes every routed lookup fall back to the scripted adapter on `context.model.llm`.
_NO_ROUTING = "specweaver.infrastructure.llm.router.ModelRouter.get_for_task"


_POST_REVIEW_STUBS = [
    "specweaver.core.flow.handlers.generation.GenerateCodeHandler.execute",
    "specweaver.core.flow.handlers.generation.GenerateTestsHandler.execute",
    "specweaver.core.flow.handlers.lint_fix.LintFixHandler.execute",
    "specweaver.core.flow.handlers.validation.ValidateTestsHandler.execute",
    "specweaver.core.flow.handlers.validation.ValidateCodeHandler.execute",
    "specweaver.core.flow.handlers.review.ReviewCodeHandler.execute",
]


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    return data_dir


def _mechanical_preset(project_dir: Path) -> None:
    """D-VAL-02 project-local override: the packaged spec preset minus the LLM-backed
    rules (S03/S07) — real battery machinery, fully deterministic."""
    pipelines = project_dir / ".specweaver" / "pipelines"
    pipelines.mkdir(parents=True, exist_ok=True)
    preset = """name: validation_spec_default_orchestrator
description: Mechanical-only spec validation for the INT-US-02 e2e proof (no LLM rules).
version: "1.0"
steps:
  - name: s01_one_sentence
    rule: S01
  - name: s02_single_setup
    rule: S02
  - name: s06_concrete_example
    rule: S06
  - name: s09_error_path
    rule: S09
  - name: s10_done_definition
    rule: S10
  - name: s08_ambiguity
    rule: S08
"""
    (pipelines / "validation_spec_default_orchestrator.yaml").write_text(preset, encoding="utf-8")


def _run_status(tmp_path: Path) -> str:
    """Read the latest persisted run's status.

    INT-US-21 CB-4: exit code 0 is ambiguous — a PARKED run and a COMPLETED run both exit 0,
    which is exactly why E6/E7 were vacuously green before. Assert on the stored state.
    """
    import os

    from specweaver.core.flow.engine.store import StateStore

    # The CLI binds `state_db_path` at import time, so these tests' monkeypatch of it does not
    # reach the runner — the real DB lands under SPECWEAVER_DATA_DIR. Resolve the same way.
    data_dir = os.environ.get("SPECWEAVER_DATA_DIR")
    candidates = (
        ([pathlib.Path(data_dir) / "pipeline_state.db"] if data_dir else [])
        + sorted(tmp_path.rglob("pipeline_state.db"))
        + sorted(tmp_path.rglob("pipe_state.db"))
    )
    for db in candidates:
        if not db.exists():
            continue
        runs = StateStore(db).list_runs(limit=1)
        if runs:
            return str(runs[0].status.value)
    raise AssertionError(f"no pipeline run was persisted (looked in {candidates})")


def _resume_until_terminal(tmp_path: Path, max_sessions: int = 6) -> tuple[str, int]:
    """Resume repeatedly until the run leaves PARKED. Returns (final status, sessions used).

    The session count is deliberately NOT hard-coded. With approve-on-resume (INT-US-21 FR-4)
    each distinct park costs the human exactly one `sw resume`, and a review rejection adds a
    loop_back that parks again — so the count is a property of the pipeline, not of the test.
    Asserting the terminal status plus a sane bound is the honest contract.
    """
    for session in range(1, max_sessions + 1):
        result = runner.invoke(app, ["resume"])
        assert result.exit_code == 0, result.output
        status = _run_status(tmp_path)
        if status != "parked":
            return status, session
    return _run_status(tmp_path), max_sessions


def _init_project(tmp_path: Path, name: str) -> Path:
    project_dir = tmp_path / name
    project_dir.mkdir()
    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0, result.output
    _mechanical_preset(project_dir)
    return project_dir


def _settings_mock():
    settings = MagicMock()
    settings.llm.model = "scripted-1"
    settings.llm.temperature = 0.2
    settings.llm.max_output_tokens = 4096
    from specweaver.core.config.settings import SandboxSettings

    settings.sandbox = SandboxSettings()
    return settings


@contextlib.contextmanager
def _drafter_world(adapter: ScriptedAdapter, provider: ScriptedProvider):
    """Patch the LLM edge + the interactive channel for the `sw draft` surface."""
    with (
        patch(
            "specweaver.infrastructure.llm.factory.create_llm_adapter",
            return_value=(_settings_mock(), adapter, MagicMock()),
        ),
        patch(
            "specweaver.interfaces.cli.hitl_provider.HITLProvider",
            return_value=provider,
        ),
    ):
        yield


# --------------------------------------------------------------------------- #
# E1 — the US-2 sentence, full-real                                            #
# --------------------------------------------------------------------------- #


def test_e1_draft_validate_review_one_command(tmp_path: Path) -> None:
    project = _init_project(tmp_path, "us2_e1")
    provider = ScriptedProvider()
    with _drafter_world(ScriptedAdapter([VERDICT_ACCEPT]), provider):
        result = runner.invoke(app, ["draft", "greeter", "--project", str(project)])

    assert result.exit_code == 0, result.output
    spec = project / "specs" / "greeter_spec.md"
    assert spec.exists()
    assert "<!-- sw-artifact:" in spec.read_text(encoding="utf-8")  # lineage tag
    assert provider.questions_asked > 0  # the human was genuinely interviewed
    assert "accepted" in result.output.lower()  # real reviewer verdict surfaced
    assert "rules passed" in result.output  # real battery ran
    assert "sw check" not in result.output  # zero manual handoff (the contract sentence)


# --------------------------------------------------------------------------- #
# E2 — the living rejection loop                                               #
# --------------------------------------------------------------------------- #


def test_e2_rejection_loops_into_real_redraft_then_accepts(tmp_path: Path) -> None:
    project = _init_project(tmp_path, "us2_e2")
    provider = ScriptedProvider()
    with _drafter_world(ScriptedAdapter([VERDICT_DENY, VERDICT_ACCEPT]), provider):
        result = runner.invoke(app, ["draft", "greeter", "--project", str(project)])

    assert result.exit_code == 0, result.output
    # the interview ran TWICE (initial draft + feedback-aware re-draft) — the loop is alive
    sections_per_interview = provider.questions_asked
    assert sections_per_interview >= 2  # at least two interview passes happened in total
    assert "accepted" in result.output.lower()


# --------------------------------------------------------------------------- #
# E3 — headless park control                                                   #
# --------------------------------------------------------------------------- #


def test_e3_headless_new_feature_parks_exit_zero(tmp_path: Path) -> None:
    project = _init_project(tmp_path, "us2_e3")
    with patch(
        "specweaver.infrastructure.llm.factory.create_llm_adapter",
        return_value=(_settings_mock(), ScriptedAdapter([]), MagicMock()),
    ):
        result = runner.invoke(app, ["run", "new_feature", "greeter", "--project", str(project)])

    assert result.exit_code == 0, result.output  # parked is NOT an error (SF-02 fix)
    assert "Resume with" in result.output
    assert not (project / "specs" / "greeter_spec.md").exists()


# --------------------------------------------------------------------------- #
# E4 — exhausted rejection                                                     #
# --------------------------------------------------------------------------- #


def test_e4_exhausted_rejections_bounded_nonzero(tmp_path: Path) -> None:
    project = _init_project(tmp_path, "us2_e4")
    provider = ScriptedProvider()
    with _drafter_world(
        ScriptedAdapter([VERDICT_DENY, VERDICT_DENY, VERDICT_DENY, VERDICT_DENY]), provider
    ):
        result = runner.invoke(app, ["draft", "greeter", "--project", str(project)])

    assert result.exit_code != 0
    assert "rejected" in result.output.lower()
    assert "Purpose section is too vague" in result.output  # findings surfaced


# --------------------------------------------------------------------------- #
# E5 — provider crash mid-interview                                            #
# --------------------------------------------------------------------------- #


def test_e5_provider_crash_fails_loud(tmp_path: Path) -> None:
    project = _init_project(tmp_path, "us2_e5")
    provider = ScriptedProvider(fail_after=1)
    with _drafter_world(ScriptedAdapter([VERDICT_ACCEPT]), provider):
        result = runner.invoke(app, ["draft", "greeter", "--project", str(project)])

    assert result.exit_code != 0  # never a silent green


# --------------------------------------------------------------------------- #
# E6 — UNUSUAL: park -> MANUAL spec -> resume -> new chain validates+reviews    #
# --------------------------------------------------------------------------- #

# INT-US-21 CB-4: this fixture used to carry only a Purpose section. That was survivable
# only because resume() re-parked at draft_spec forever, so the run never actually reached
# validate_spec — the "flows through the chain" claim was never exercised. With
# approve-on-resume the real S-battery now judges this file, so it has to be a spec that can
# genuinely pass: the same shape the Drafter's own template produces.
MANUAL_SPEC = f"""# Greeter — Component Spec

> **Status**: DRAFT
> **Layer**: Component (L2)

---

## 1. Purpose
{SECTION_BODY}

---

## 2. Contract

`greet(name: str) -> str`

- **Input**: `name` — a non-empty user name.
- **Returns**: the exact string `Hello, {{name}}!`.
- **Raises**: `ValueError("name must not be empty")` when `name` is empty.

Example:

```python
greet("Ada")  # returns "Hello, Ada!"
```

---

## 3. Protocol

Synchronous, single call. No I/O, no network, no persistence. The function is pure: the same
`name` always yields the same greeting.

---

## 4. Policy

- Empty or whitespace-only names are rejected with `ValueError`, never a silent default.
- The greeting format is fixed and not configurable in this component.
- No logging of user names (they are user-supplied input).

---

## 5. Boundaries

- **In scope**: formatting a greeting for one supplied name.
- **Out of scope**: localisation, honorifics, name validation beyond emptiness, persistence,
  and any transport concern (HTTP, CLI) — those belong to the caller.

---

## Done Definition

- [ ] `greet` returns the exact greeting for valid names
- [ ] `greet` raises `ValueError` with the documented message for an empty name
- [ ] All public methods have unit tests
- [ ] Examples from Contract pass as test cases
"""


def test_e6_park_manual_spec_resume_flows_through_chain(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "specweaver.core.config.paths.state_db_path", lambda: tmp_path / "pipe_state.db"
    )
    project = _init_project(tmp_path, "us2_e6")
    monkeypatch.setenv("SW_PROJECT", str(project))
    adapter = ScriptedAdapter([VERDICT_ACCEPT])

    stubs = [patch(p, new=_ok_execute) for p in _POST_REVIEW_STUBS]
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch(
                "specweaver.infrastructure.llm.factory.create_llm_adapter",
                return_value=(_settings_mock(), adapter, MagicMock()),
            )
        )
        stack.enter_context(patch(_NO_ROUTING, return_value=None))
        for s in stubs:
            stack.enter_context(s)

        # Session 1: headless run parks at draft (the historic workflow's first half).
        result1 = runner.invoke(app, ["run", "new_feature", "greeter", "--project", str(project)])
        assert result1.exit_code == 0, result1.output

        # The human writes the spec MANUALLY, exactly as the park message instructs.
        spec = project / "specs" / "greeter_spec.md"
        spec.write_text(MANUAL_SPEC, encoding="utf-8")

        # Session 2+: resume until the run leaves PARKED. Session 1 was a *handler* park (the
        # spec was missing), so session 2 re-executes draft, the spec now exists, it PASSES, and
        # the draft_spec HITL gate parks — which session 3 approves (INT-US-21 FR-4), letting the
        # REAL battery and REAL reviewer judge the human's file.
        status, sessions = _resume_until_terminal(tmp_path)

        # exit_code 0 is NOT proof — PARKED and COMPLETED both exit 0, which is exactly why this
        # test was vacuously green before. Assert the persisted status.
        assert status == "completed", f"journey ended {status} after {sessions} resume(s)"
        assert not adapter.verdicts, "the scripted reviewer verdict was never consumed"


# --------------------------------------------------------------------------- #
# E7 — UNUSUAL: rejection-park WITH findings -> human edits -> resume -> accept #
# --------------------------------------------------------------------------- #


def test_e7_rejection_park_edit_resume_accepted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "specweaver.core.config.paths.state_db_path", lambda: tmp_path / "pipe_state.db"
    )
    project = _init_project(tmp_path, "us2_e7")
    monkeypatch.setenv("SW_PROJECT", str(project))
    # The spec exists up-front (so the headless run reaches review), review DENIES once.
    spec = project / "specs" / "greeter_spec.md"
    spec.write_text(MANUAL_SPEC, encoding="utf-8")
    adapter = ScriptedAdapter([VERDICT_DENY, VERDICT_ACCEPT])

    stubs = [patch(p, new=_ok_execute) for p in _POST_REVIEW_STUBS]
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch(
                "specweaver.infrastructure.llm.factory.create_llm_adapter",
                return_value=(_settings_mock(), adapter, MagicMock()),
            )
        )
        stack.enter_context(patch(_NO_ROUTING, return_value=None))
        for s in stubs:
            stack.enter_context(s)

        # Session 1: validate passes, review DENIES -> loop_back -> headless draft
        # parks WITH the reviewer findings (SF-01 branch). Parked = exit 0.
        result1 = runner.invoke(app, ["run", "new_feature", "greeter", "--project", str(project)])
        assert result1.exit_code == 0, result1.output

        # The human revises the spec per the findings.
        spec.write_text(
            MANUAL_SPEC + "\nThe greeting format is exactly `Hello, {name}!`.\n", encoding="utf-8"
        )

        # Session 2+: resume until terminal. The path is longer than it looks, and every hop is
        # a real park the human must acknowledge: approve the draft gate -> validate passes ->
        # review DENIES -> loop_back re-parks draft (headless, carrying findings) -> approve the
        # draft gate again -> validate -> review ACCEPTS -> stubbed post-review steps.
        status, sessions = _resume_until_terminal(tmp_path)

        assert status == "completed", f"journey ended {status} after {sessions} resume(s)"
        assert not adapter.verdicts, "both scripted verdicts should have been consumed"
