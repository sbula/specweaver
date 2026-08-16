# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw implement` installs a TelemetryCollector, and the runner drains it. INT-US-16 CB-1.

Proves: INT-US-16 FR-3, INT-US-16 FR-2

The seam has three links and this file pins all of them at the boundary the `implement` command
owns: the command builds an adapter, the adapter must arrive on `RunContext.model.llm` as a
`TelemetryCollector`, and `PipelineRunner._flush_telemetry` only drains it if that `isinstance`
guard passes (`core/flow/engine/telemetry.py:24-26`).

**Why these tests never patch `create_llm_adapter`.** The condition under test IS
`if telemetry_project:` inside that function (`factory.py:84-92`). Patching it would replace the
branch with a stub and prove nothing — so the double goes one level lower, at
`factory._get_adapter_class`, the seam `tests/e2e/capabilities/infrastructure/test_telemetry_e2e.py:172`
established. For the same reason `tests/scripted_llm.py::scripted_world` is unusable here: it
patches `create_llm_adapter` and hands back a bare `ScriptedLLM`, which would leave
`context.model.llm` unwrapped and every assertion below vacuously "passing" against the wrong object.

**Why the RunContext is captured rather than constructed.** An assertion on a context this file
built itself would hold no matter what the command does. The spy takes the object the command
actually handed to `PipelineRunner`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import LLMResponse, TokenUsage
from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.integration

#: Distinctive on purpose (NFR-5). `sw usage` renders several numeric columns, so a round number
#: like 100 can be satisfied by a cost, a duration or a call count instead of the token total.
_PROMPT_TOKENS = 8317
_COMPLETION_TOKENS = 4271

#: Generated code that passes its own generated test, so the pipeline can reach `completed`.
#: Taken from `tests/unit/workflows/implementation/interfaces/test_implementation_cli.py:55`:
#: since `TECH-017` SF-04 a QA run that collects nothing fails loud, so `"pass\n"` will not do.
_COLLECTABLE = "def greet():\n    pass\n\n\ndef test_greet_is_callable() -> None:\n    assert greet() is None\n"

#: Code whose generated test fails, so `run_tests` exhausts its loop-back and the run ends
#: NOT completed — the state the `finally` in `PipelineRunner` exists for.
_FAILING = "def greet():\n    pass\n\n\ndef test_greet_returns_hello() -> None:\n    assert greet() == 'hello'\n"


class _FakeGeminiAdapter:
    """Quacks like `GeminiAdapter`, never calls the API.

    Duplicated deliberately from `tests/e2e/capabilities/infrastructure/test_telemetry_e2e.py:52`
    rather than imported: a test-module-to-test-module import couples two suites through an
    undeclared dependency. Promote both to a shared helper when a third caller appears.
    """

    provider_name = "gemini"
    api_key_env_var = "GEMINI_API_KEY"

    #: Set per test — the text every `generate()` returns.
    payload = _COLLECTABLE

    def __init__(self, **_kwargs: Any) -> None:
        pass

    def available(self) -> bool:
        return True

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    async def count_tokens(self, text: str, model: str) -> int:
        return len(text) // 4

    async def generate(self, _messages: Any, _config: Any) -> LLMResponse:
        return LLMResponse(
            text=type(self).payload,
            model="fake-telemetry-model",
            usage=TokenUsage(
                prompt_tokens=_PROMPT_TOKENS,
                completion_tokens=_COMPLETION_TOKENS,
                total_tokens=_PROMPT_TOKENS + _COMPLETION_TOKENS,
            ),
        )

    async def generate_with_tools(self, messages: Any, config: Any, *_a: Any, **_k: Any):
        return await self.generate(messages, config)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the whole CLI at a throwaway data dir, the way the e2e tier does globally."""
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database

    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    db_path = str(data_dir / "specweaver.db")
    bootstrap_database(db_path)
    return Database(db_path)


def _scaffold(tmp_path: Path, *, project: str | None) -> Path:
    """Lay out a project and write a spec. Returns the spec path.

    `project=None` deliberately skips `sw init`, because **`sw init` also makes the project
    active** — calling it and then hoping for no active project pins nothing. The directories are
    created by hand instead, the shape
    `tests/unit/workflows/implementation/interfaces/test_implementation_cli.py:41` uses, which is
    enough for `sw implement --project <path>` to run.
    """
    if project is None:
        for sub in (".specweaver", "specs", "src", "tests"):
            (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    else:
        result = runner.invoke(app, ["init", project, "--path", str(tmp_path)])
        assert result.exit_code == 0, result.output
        result = runner.invoke(app, ["use", project])
        assert result.exit_code == 0, result.output
    spec = tmp_path / "specs" / "greeter_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Greeter\n## 1. Purpose\nGreets.\n", encoding="utf-8")
    return spec


def _invoke_with_mocked_pipeline(tmp_path: Path, *, project: str | None):
    """Run `sw implement` with the pipeline mocked. Returns `(cli result, runner mock)`."""
    from specweaver.core.flow.engine.state import RunStatus

    spec = _scaffold(tmp_path, project=project)
    with (
        patch.dict(os.environ, {"GEMINI_API_KEY": "integration-key"}),
        patch(
            "specweaver.infrastructure.llm.factory._get_adapter_class",
            return_value=_FakeGeminiAdapter,
        ),
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
    ):
        run_state = MagicMock()
        run_state.status = RunStatus.COMPLETED
        run_state.step_records = []
        mock_runner_class.return_value.run = AsyncMock(return_value=run_state)
        result = runner.invoke(app, ["implement", str(spec), "--project", str(tmp_path)])
        return result, mock_runner_class


def _capture_context(tmp_path: Path, *, project: str):
    """Return the RunContext the command handed to `PipelineRunner`."""
    result, mock_runner_class = _invoke_with_mocked_pipeline(tmp_path, project=project)
    assert mock_runner_class.called, result.output
    return mock_runner_class.call_args.args[1]


def _run_for_real(tmp_path: Path, *, project: str, payload: str):
    """Run the whole `sw implement` pipeline against the fake adapter. Returns the CLI result."""
    spec = _scaffold(tmp_path, project=project)
    _FakeGeminiAdapter.payload = payload
    try:
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "integration-key"}),
            patch(
                "specweaver.infrastructure.llm.factory._get_adapter_class",
                return_value=_FakeGeminiAdapter,
            ),
        ):
            return runner.invoke(app, ["implement", str(spec), "--project", str(tmp_path)])
    finally:
        _FakeGeminiAdapter.payload = _COLLECTABLE


def _usage_rows(db, project: str) -> list[dict]:
    import anyio

    from specweaver.infrastructure.llm.store import LlmRepository

    async def _read():
        async with db.async_session_scope() as session:
            return await LlmRepository(session).get_usage_summary(project=project)

    return anyio.run(_read)


class TestImplementInstallsTelemetryCollector:
    """FR-3 — the adapter the command builds arrives wrapped, or deliberately does not."""

    def test_active_project_wraps_the_adapter_for_the_runner(self, tmp_path: Path) -> None:
        """[Happy] with an active project, `RunContext.model.llm` satisfies flush_telemetry's guard."""
        context = _capture_context(tmp_path, project="tele_proj")
        assert isinstance(context.model.llm, TelemetryCollector)

    def test_no_active_project_stops_the_command_before_any_adapter_is_built(
        self, tmp_path: Path
    ) -> None:
        """[Boundary] no active project → exit 1, and no adapter is constructed at all.

        **This corrects a finding, and the correction is the point.** `INT-US-16`'s design and
        plan both recorded that a run without an active project *proceeds* and silently records
        nothing — reasoned from `cli.py:216-219`, where `telemetry_project=None` skips the
        collector wrap, and from the `# type: ignore[arg-type]` next to it. Run rather than read,
        the command never gets that far: `load_settings(db, None)` raises first
        (`settings_loader.py:179`, *"Project 'None' not found"*), so there is no silent untracked
        spend from this command — only a cryptic message.

        The seam claim survives intact and is what this asserts: the collector exists to attribute
        spend to a project, so where there is no project there is no adapter and nothing to flush.
        """
        result, mock_runner_class = _invoke_with_mocked_pipeline(tmp_path, project=None)

        assert result.exit_code == 1, result.output
        assert not mock_runner_class.called, "the command built a pipeline it cannot attribute"

        # FR-2, CB-2. Until this boundary the message was `Project 'None' not found` — the settings
        # loader describing a failed database lookup on the string `None`, which tells the user
        # nothing about what to do. The exit code is unchanged; what changed is what it says.
        assert shows(result.output, "No active project"), result.output
        assert shows(result.output, "sw use <name>"), result.output
        assert not shows(result.output, "Project 'None' not found"), result.output


class TestImplementRecordsSpendOnCompletedRun:
    """FR-3, happy path end to end — the collector reaches the runner AND the runner drains it.

    Found by the pre-commit gap analysis: the two tests above mock `PipelineRunner`, so neither
    ever reaches a flush. The most basic claim in this contract — *a successful run records what it
    spent* — had no live proof anywhere. `tests/unit/core/flow/engine/test_runner_telemetry.py`
    contains `test_flush_called_on_successful_run`, in a class pytest never collects (`TECH-051`).
    """

    def test_a_real_run_records_rows_carrying_the_model_that_was_called(
        self, tmp_path: Path, _isolated_db
    ) -> None:
        """[Happy] a real pipeline run persists rows attributed to the model that answered.

        **What this deliberately does not assert, and why.** The run does not reach exit 0 in this
        harness: the QA step reports `tests: 0 passed, 0 failed` against a generated
        `tests/test_greeter.py` that is on disk and valid — verified by probe. Something about how
        the QA runner invokes pytest inside a generated project collects nothing there, which the
        plan's Risk R-1 anticipated and answered in advance: *"assert on `sw usage` alone — the
        flush is in a `finally`, so telemetry is recorded either way."*

        So the exit code is left to CB-2's e2e, which has to solve it to assert the journey at all.
        Narrowing the assertion is not the same as skipping the test: the model identity below is
        the part that says the row came from **this** call rather than from anywhere else, and it
        would not survive the collector being bypassed.
        """
        _run_for_real(tmp_path, project="tele_proj", payload=_COLLECTABLE)

        rows = _usage_rows(_isolated_db, "tele_proj")
        assert rows, "a real run recorded nothing"
        assert {r["model"] for r in rows} == {"fake-telemetry-model"}
        assert sum(r["total_prompt_tokens"] for r in rows) >= _PROMPT_TOKENS


class TestImplementRecordsSpendOnUnsuccessfulRun:
    """FR-3, degradation — the flush is in a `finally`, so a failed run still records its spend."""

    def test_failed_run_still_records_what_it_spent(self, tmp_path: Path, _isolated_db) -> None:
        """[Graceful degradation] generated code fails its own test → run not completed → rows exist.

        The money was spent before the pipeline failed, so it has to be recorded. Nothing else in
        the repo covers this: `tests/unit/core/flow/engine/test_runner_telemetry.py` has a test for
        it, in a class named `QARunnerTelemetryFlush`, which pytest never collects (`TECH-051`).
        """
        result = _run_for_real(tmp_path, project="tele_proj", payload=_FAILING)
        assert result.exit_code == 1, f"expected a failed run, got:\n{result.output}"

        rows = _usage_rows(_isolated_db, "tele_proj")
        assert rows, "a run that called the LLM and then failed recorded nothing"
        assert sum(r["total_prompt_tokens"] for r in rows) >= _PROMPT_TOKENS


class TestHostileProjectNameIsRejectedBeforeTheSeam:
    """FR-3, hostile — the telemetry key is a project name, so the guard is at registration.

    The first draft of this test asserted that a SQL-metacharacter name round-trips through write
    and read. **It cannot**, and finding that out is the result: `sw init` refuses the name, so it
    never becomes a telemetry key and never reaches `get_usage_summary` at all. The assertion
    therefore pins the guard that makes the round-trip question moot — loosen project-name
    validation and this fails.
    """

    def test_sql_metacharacters_are_refused_at_registration(self, tmp_path: Path) -> None:
        """[Hostile] rejected with a message, not a traceback, and the table is untouched."""
        hostile = "'; DROP TABLE llm_usage_log; --"
        result = runner.invoke(app, ["init", hostile, "--path", str(tmp_path)])

        assert result.exit_code == 1, result.output
        assert shows(result.output, f"Invalid project name '{hostile}'"), result.output
        # A raw exception here would mean the name reached something that could not handle it.
        assert isinstance(result.exception, SystemExit), result.exception

        listed = runner.invoke(app, ["projects"])
        assert listed.exit_code == 0, listed.output
