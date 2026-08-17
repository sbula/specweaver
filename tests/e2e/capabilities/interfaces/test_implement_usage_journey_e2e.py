# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a run spent is visible in `sw usage`. INT-US-16 CB-1.

Proves: INT-US-16 FR-1, INT-US-16 FR-4

**Why FR-1 is only the token half.** The design wrote the US-16 journey as one e2e asserting tokens
*and* a USD figure priced from `sw costs set`. Those are two claims, and only one of them holds:
no command passes `cost_overrides` into `create_llm_adapter` (`factory.py:43` accepts the keyword;
`cli.py:219`, `flow/interfaces/cli.py:96` and `review/…/cli.py:195,293` all omit it), so a rate the
user configures is echoed back by `sw costs` and then ignored. Splitting the FR is not a softening —
the token half is the larger half of *"see exactly how much each agent is spending"*, it works
today, and it deserves a live proof rather than being held hostage to the pricing bug. FR-1b, the
USD half, is **FR-4** and CB-2's red.

**The seam this closes.** Before this file the write half was proven from the factory down to DB
rows and the read half from a hand-written `sqlite3` INSERT up to `sw usage`
(`test_cli_decentralized_e2e.py:96-107`), with nothing crossing the middle. If the writer's column
set drifted, both halves stayed green.

**What is deliberately not patched.** `create_llm_adapter` runs for real, so the
`if telemetry_project:` branch that installs the collector is exercised rather than replaced; the
double sits one level lower at `factory._get_adapter_class`. `tests/scripted_llm.py::scripted_world`
is unusable here for the same reason — it patches the factory and hands back a bare `ScriptedLLM`,
leaving `context.model.llm` unwrapped and the assertions below passing against nothing.

**DB isolation** comes from `tests/e2e/conftest.py::_isolate_env` (`autouse`, sets
`SPECWEAVER_DATA_DIR`) — the command resolves its own database. This file must NOT copy
`test_cli_decentralized_e2e.py`'s `_patch_config_path`, which monkeypatches `_core.get_db` and so
takes DB resolution out of the very journey under test.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse, TokenUsage
from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

#: Distinctive on purpose. `sw usage` renders call count, both token columns, a total, a USD figure
#: and a duration, so a round number can be satisfied by the wrong column (NFR-5).
_PROMPT_TOKENS = 9137
_COMPLETION_TOKENS = 3271
_TOTAL_TOKENS = _PROMPT_TOKENS + _COMPLETION_TOKENS

_MODEL = "fake-journey-model"

#: Valid as either the generated module or the generated test: since `TECH-017` SF-04 a QA run that
#: collects nothing fails loud, so a bare `pass` will not do.
_COLLECTABLE = "def greet():\n    pass\n\n\ndef test_greet_is_callable() -> None:\n    assert greet() is None\n"


class _FakeGeminiAdapter:
    """Quacks like `GeminiAdapter`, never calls the API.

    Duplicated from `tests/e2e/capabilities/infrastructure/test_telemetry_e2e.py:52` rather than
    imported: a test-module-to-test-module import couples two suites through an undeclared
    dependency. Promote to a shared helper when a third caller wants it.
    """

    provider_name = "gemini"
    api_key_env_var = "GEMINI_API_KEY"

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
            text=_COLLECTABLE,
            model=_MODEL,
            usage=TokenUsage(
                prompt_tokens=_PROMPT_TOKENS,
                completion_tokens=_COMPLETION_TOKENS,
                total_tokens=_TOTAL_TOKENS,
            ),
        )

    async def generate_with_tools(self, messages: Any, config: Any, *_a: Any, **_k: Any):
        return await self.generate(messages, config)


def _total_token_cells(output: str) -> list[int]:
    """Every `Total Tokens` value in a rendered `sw usage` table.

    The column sits between `Completion Tokens` and `Cost (USD)`, so it is the third of the four
    comma-formatted integers on a data row. Parsing beats asserting a literal: the row is an
    aggregate over however many calls the pipeline happened to make.
    """
    found: list[int] = []
    for line in output.splitlines():
        if not line.startswith("│"):
            continue
        cells = [c.strip() for c in line.strip("│").split("│")]
        numbers = [c for c in cells if re.fullmatch(r"[\d,]+", c)]
        if len(numbers) >= 4:
            found.append(int(numbers[3].replace(",", "")))
    return found


def _cost_cells(output: str) -> list[str]:
    """Every `Cost (USD)` cell in a rendered `sw usage` table, as printed.

    Returned raw rather than parsed: Rich truncates the column, so `$0.00000` and `$12408.0` both
    arrive shortened. The LEADING characters survive, which is why FR-4's rate is chosen large
    enough that a priced row and an unpriced one differ in their first two characters.
    """
    found: list[str] = []
    for line in output.splitlines():
        if not line.startswith("│"):
            continue
        cells = [c.strip() for c in line.strip("│").split("│")]
        found.extend(c for c in cells if c.startswith("$"))
    return found


class TestImplementSpendIsVisibleInUsage:
    """The US-16 benefit, end to end: run a command, then ask what it cost."""

    def test_a_run_records_tokens_that_sw_usage_then_displays(self, tmp_path: Path) -> None:
        """[Happy] `sw init` → `sw use` → `sw implement` → `sw usage` shows THAT run's tokens."""
        assert runner.invoke(app, ["init", "journey_proj", "--path", str(tmp_path)]).exit_code == 0
        assert runner.invoke(app, ["use", "journey_proj"]).exit_code == 0

        spec = tmp_path / "specs" / "greeter_spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text("# Greeter\n## 1. Purpose\nGreets.\n", encoding="utf-8")

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "e2e-journey-key"}),
            patch(
                "specweaver.infrastructure.llm.factory._get_adapter_class",
                return_value=_FakeGeminiAdapter,
            ),
        ):
            runner.invoke(app, ["implement", str(spec), "--project", str(tmp_path)])

        usage = runner.invoke(app, ["usage"])
        assert usage.exit_code == 0, usage.output

        # `sw usage` prints "No usage data recorded" and still exits 0, so the exit code proves
        # nothing on its own (NFR-5). The token arithmetic below is what carries this test.
        #
        # **The model name is deliberately NOT asserted.** Rich truncates cells to the terminal
        # width, so it renders as `fake-j…`, and passing `COLUMNS` to `invoke()` does not help: the
        # CLI's `Console` is constructed at module IMPORT (`interfaces/cli/_core.py:37`), which is
        # before any test can set an environment variable. An earlier draft asserted the full name,
        # passed when run alone and failed under `-n auto`, where xdist's import-time width is
        # narrower — the same import-time-Console trap `TECH-050` was written for.
        #
        # The pipeline makes several LLM calls and `sw usage` aggregates per task type, so no single
        # row equals one call. Every call returns the same usage, so each row's total must be an
        # exact multiple of it — which a zero row, a truncated row, or a row from anywhere else
        # cannot satisfy, and which no terminal width can change.
        totals = _total_token_cells(usage.output)
        assert totals, f"no Total Tokens cell parsed from:\n{usage.output}"
        assert all(n > 0 and n % _TOTAL_TOKENS == 0 for n in totals), totals

    def test_usage_attributes_the_run_to_the_active_project_only(self, tmp_path: Path) -> None:
        """[Boundary] a second project that ran nothing shows none of the first one's spend."""
        assert runner.invoke(app, ["init", "journey_proj", "--path", str(tmp_path)]).exit_code == 0
        assert runner.invoke(app, ["use", "journey_proj"]).exit_code == 0

        spec = tmp_path / "specs" / "greeter_spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text("# Greeter\n## 1. Purpose\nGreets.\n", encoding="utf-8")

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "e2e-journey-key"}),
            patch(
                "specweaver.infrastructure.llm.factory._get_adapter_class",
                return_value=_FakeGeminiAdapter,
            ),
        ):
            runner.invoke(app, ["implement", str(spec), "--project", str(tmp_path)])

        other = tmp_path / "other"
        other.mkdir()
        assert runner.invoke(app, ["init", "quiet_proj", "--path", str(other)]).exit_code == 0
        assert runner.invoke(app, ["use", "quiet_proj"]).exit_code == 0

        usage = runner.invoke(app, ["usage"])
        assert usage.exit_code == 0, usage.output

        # Asserting the model name is ABSENT would be vacuous: Rich truncates it to `fake-j…`, so
        # the assertion would hold whether or not the row were there. The row count is the honest
        # question, and it is width-independent.
        assert _total_token_cells(usage.output) == [], usage.output
        assert shows(usage.output, "No usage data recorded"), usage.output


class TestConfiguredRateReachesTheRun:
    """FR-4 — a rate set with `sw costs set` prices what `sw usage` reports.

    **Red when written, and for the right reason.** `create_llm_adapter` has always accepted
    `cost_overrides` (`factory.py:43`), and no command has ever passed it: `cli.py:219`,
    `flow/interfaces/cli.py:96` and `review/…/cli.py:195,293` all omit the keyword, and the only
    reader of `LlmRepository.get_cost_overrides()` in `src/` is `sw costs` itself, for display. So
    the user sets a price, `sw costs` echoes it back, and every run prices from the built-in table —
    or `0.0` for a model absent from it, with the fact buried in a `logger.warning`.
    """

    #: Large on purpose. Rich truncates the Cost column, so `$0.00000` and a priced figure must
    #: differ in their FIRST characters to be told apart at any terminal width.
    _RATE_PER_1K = 1000.0

    def test_the_rate_the_user_set_is_the_rate_that_is_reported(self, tmp_path: Path) -> None:
        """[Happy] `sw costs set` → `sw implement` → `sw usage` shows a priced, non-zero cost."""
        assert runner.invoke(app, ["init", "journey_proj", "--path", str(tmp_path)]).exit_code == 0
        assert runner.invoke(app, ["use", "journey_proj"]).exit_code == 0
        priced = runner.invoke(
            app, ["costs", "set", _MODEL, str(self._RATE_PER_1K), str(self._RATE_PER_1K)]
        )
        assert priced.exit_code == 0, priced.output

        spec = tmp_path / "specs" / "greeter_spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text("# Greeter\n## 1. Purpose\nGreets.\n", encoding="utf-8")

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "e2e-journey-key"}),
            patch(
                "specweaver.infrastructure.llm.factory._get_adapter_class",
                return_value=_FakeGeminiAdapter,
            ),
        ):
            runner.invoke(app, ["implement", str(spec), "--project", str(tmp_path)])

        usage = runner.invoke(app, ["usage"])
        assert usage.exit_code == 0, usage.output

        costs = _cost_cells(usage.output)
        assert costs, f"no Cost cell parsed from:\n{usage.output}"
        assert all(not c.startswith("$0") for c in costs), (
            f"the configured rate never reached the run — costs read {costs}"
        )
