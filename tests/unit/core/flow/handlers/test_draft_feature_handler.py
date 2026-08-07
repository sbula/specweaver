# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for draft+feature — INT-US-21 SF-01 CB-1 (FR-1).

The handler wraps the shipped ``FeatureDrafter`` with full ``DraftSpecHandler`` parity and
reconciles the drafter's self-derived output path against ``context.spec_path``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.draft import (
    DraftFeatureHandler,
    DraftSpecHandler,
    _pop_step_feedback,
)
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from pathlib import Path


def _step(**params: Any) -> PipelineStep:
    return PipelineStep(
        name="draft_feature",
        action=StepAction.DRAFT,
        target=StepTarget.FEATURE,
        params=params,
    )


def _interactive_ctx(tmp_path: Path, spec: Path) -> RunContext:
    """A context with both an LLM and a provider — the drafting path is reachable."""
    ctx = RunContext(project_path=tmp_path, spec_path=spec)
    ctx.model = ctx.model.model_copy(update={"llm": AsyncMock()})
    ctx.context_provider = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestDraftFeatureHappyPath:
    @pytest.mark.asyncio
    async def test_existing_feature_spec_skips_and_passes(self, tmp_path: Path) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        spec.write_text("# Greeter\n", encoding="utf-8")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)

        result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.PASSED
        assert "greeter_feature_spec.md" in result.output["message"]

    @pytest.mark.asyncio
    async def test_exists_skip_extracts_artifact_uuid(self, tmp_path: Path) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        known = "3f2b8c1e-9d4a-4c7b-8e6f-1a2b3c4d5e6f"
        spec.write_text(f"<!-- sw-artifact: {known} -->\n# Greeter\n", encoding="utf-8")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)

        result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.PASSED
        assert result.artifact_uuid == known

    @pytest.mark.asyncio
    async def test_drafting_returns_the_context_spec_path(self, tmp_path: Path) -> None:
        """The drafter's self-derived path must come back as exactly context.spec_path."""
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)

        async def fake_draft(_self, name, output_dir, **_kwargs):
            written = output_dir / f"{name}_feature_spec.md"
            written.write_text("# Drafted\n", encoding="utf-8")
            return written

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
            new=fake_draft,
        ):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.PASSED, result.error_message
        assert result.output["path"] == str(spec)
        assert spec.exists()

    @pytest.mark.asyncio
    async def test_drafter_receives_stem_derived_name_and_parent_dir(self, tmp_path: Path) -> None:
        """name = the '_feature_spec.md' prefix; output_dir = spec_path.parent."""
        nested = tmp_path / "specs" / "sub"
        nested.mkdir(parents=True)
        spec = nested / "sell_shares_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)
        seen: dict[str, Any] = {}

        async def fake_draft(_self, name, output_dir, **_kwargs):
            seen["name"] = name
            seen["output_dir"] = output_dir
            spec.write_text("# Drafted\n", encoding="utf-8")
            return spec

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
            new=fake_draft,
        ):
            await DraftFeatureHandler().execute(_step(), ctx)

        assert seen["name"] == "sell_shares"
        assert seen["output_dir"] == nested


class TestRegistryCompleteness:
    """T1.6 — the bundled feature_decomposition pipeline must find real handlers."""

    def test_draft_feature_is_registered(self) -> None:
        assert StepHandlerRegistry().get(StepAction.DRAFT, StepTarget.FEATURE) is not None

    def test_validate_feature_is_registered(self) -> None:
        assert StepHandlerRegistry().get(StepAction.VALIDATE, StepTarget.FEATURE) is not None

    def test_draft_feature_resolves_to_the_feature_handler(self) -> None:
        handler = StepHandlerRegistry().get(StepAction.DRAFT, StepTarget.FEATURE)
        assert isinstance(handler, DraftFeatureHandler)


# ---------------------------------------------------------------------------
# Boundary / edge cases
# ---------------------------------------------------------------------------


class TestDraftFeatureBoundaries:
    @pytest.mark.asyncio
    async def test_spec_path_without_feature_suffix_errors_loudly(self, tmp_path: Path) -> None:
        """`foo.md` cannot round-trip through FeatureDrafter — fail before any LLM setup."""
        spec = tmp_path / "greeter.md"
        ctx = _interactive_ctx(tmp_path, spec)

        result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.ERROR
        assert "_feature_spec.md" in result.error_message

    @pytest.mark.asyncio
    async def test_plain_spec_suffix_is_rejected(self, tmp_path: Path) -> None:
        """`greeter_spec.md` is the component convention, not the feature one."""
        spec = tmp_path / "greeter_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)

        result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.ERROR
        assert "_feature_spec.md" in result.error_message

    @pytest.mark.asyncio
    async def test_empty_derived_name_errors(self, tmp_path: Path) -> None:
        """`_feature_spec.md` passes the suffix check but yields an empty feature name."""
        spec = tmp_path / "_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)

        result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.ERROR

    @pytest.mark.asyncio
    async def test_suffix_guard_runs_before_any_drafting(self, tmp_path: Path) -> None:
        """A bad name must cost zero LLM calls."""
        spec = tmp_path / "greeter.md"
        ctx = _interactive_ctx(tmp_path, spec)
        drafter = AsyncMock()

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft", new=drafter
        ):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.ERROR
        drafter.assert_not_awaited()


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


class TestDraftFeatureDegradation:
    @pytest.mark.asyncio
    async def test_drafter_exception_becomes_error_result(self, tmp_path: Path) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)

        async def boom(*_args, **_kwargs):
            raise RuntimeError("provider exploded")

        with patch("specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft", new=boom):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.ERROR
        assert "provider exploded" in result.error_message

    @pytest.mark.asyncio
    async def test_drafter_returning_a_different_path_errors(self, tmp_path: Path) -> None:
        """The round-trip guard: if FeatureDrafter ever changes its naming, fail loudly."""
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)
        stray = tmp_path / "somewhere_else.md"

        async def fake_draft(*_args, **_kwargs):
            stray.write_text("# Drafted\n", encoding="utf-8")
            return stray

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
            new=fake_draft,
        ):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.ERROR

    @pytest.mark.asyncio
    async def test_correct_path_but_no_file_written_errors(self, tmp_path: Path) -> None:
        """Drafter claims success at the right path but wrote nothing → fail here, not later."""
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)

        async def fake_draft(_self, *_args, **_kwargs):
            return spec  # deliberately writes nothing

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
            new=fake_draft,
        ):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.ERROR
        assert "no file exists" in result.error_message
        assert not spec.exists()

    @pytest.mark.asyncio
    async def test_unset_db_still_passes(self, tmp_path: Path) -> None:
        """No telemetry DB configured -> lineage logging is skipped, drafting still succeeds."""
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)
        assert ctx.db is None

        async def fake_draft(*_args, **_kwargs):
            spec.write_text("# Drafted\n", encoding="utf-8")
            return spec

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
            new=fake_draft,
        ):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.PASSED, result.error_message

    @pytest.mark.asyncio
    async def test_unknown_render_profile_errors(self, tmp_path: Path) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)

        result = await DraftFeatureHandler().execute(_step(render_profile="not_a_profile"), ctx)

        assert result.status == StepStatus.ERROR


# ---------------------------------------------------------------------------
# Hostile / wrong input
# ---------------------------------------------------------------------------


class TestDraftFeatureHostile:
    @pytest.mark.asyncio
    async def test_directory_at_spec_path_errors(self, tmp_path: Path) -> None:
        """A directory must not be read_text()'d nor silently drafted over."""
        spec = tmp_path / "greeter_feature_spec.md"
        spec.mkdir()
        ctx = RunContext(project_path=tmp_path, spec_path=spec)

        result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.ERROR

    @pytest.mark.asyncio
    async def test_headless_without_provider_parks(self, tmp_path: Path) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = RunContext(project_path=tmp_path, spec_path=spec)

        result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.WAITING_FOR_INPUT
        assert str(spec) in result.output["message"]

    @pytest.mark.asyncio
    async def test_llm_present_but_no_provider_parks(self, tmp_path: Path) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        ctx.model = ctx.model.model_copy(update={"llm": AsyncMock()})

        result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.WAITING_FOR_INPUT

    @pytest.mark.asyncio
    async def test_derived_name_can_never_contain_a_path_separator(self, tmp_path: Path) -> None:
        """Traversal cannot be introduced by the derivation: name comes from Path.name."""
        nested = tmp_path / "specs"
        nested.mkdir()
        spec = nested / "..__..__etc_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)
        seen: dict[str, Any] = {}

        async def fake_draft(_self, name, output_dir, **_kwargs):
            seen["name"] = name
            spec.write_text("# Drafted\n", encoding="utf-8")
            return spec

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
            new=fake_draft,
        ):
            await DraftFeatureHandler().execute(_step(), ctx)

        assert "/" not in seen["name"]
        assert "\\" not in seen["name"]


# ---------------------------------------------------------------------------
# Feedback parity (loop_back re-entry)
# ---------------------------------------------------------------------------


class TestDraftFeatureFeedbackParity:
    @pytest.mark.asyncio
    async def test_headless_feedback_parks_carrying_findings(self, tmp_path: Path) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        spec.write_text("# Greeter\n", encoding="utf-8")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        ctx.feedback = {"draft_feature": {"from_step": "review", "findings": {"issue": "vague"}}}

        result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.WAITING_FOR_INPUT
        assert result.output["reviewer_findings"] == {"issue": "vague"}

    @pytest.mark.asyncio
    async def test_feedback_is_popped_exactly_once(self, tmp_path: Path) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        spec.write_text("# Greeter\n", encoding="utf-8")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        ctx.feedback = {"draft_feature": {"from_step": "review", "findings": {"issue": "vague"}}}

        await DraftFeatureHandler().execute(_step(), ctx)

        assert "draft_feature" not in ctx.feedback

    @pytest.mark.asyncio
    async def test_feedback_beats_exists_skip(self, tmp_path: Path) -> None:
        """Without this, the rejection loop is dead: the spec exists, so it would skip."""
        spec = tmp_path / "greeter_feature_spec.md"
        spec.write_text("# Greeter\n", encoding="utf-8")
        ctx = _interactive_ctx(tmp_path, spec)
        ctx.feedback = {"draft_feature": {"from_step": "review", "findings": {"issue": "vague"}}}
        redrafted = False

        async def fake_draft(*_args, **_kwargs):
            nonlocal redrafted
            redrafted = True
            return spec

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
            new=fake_draft,
        ):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert redrafted, "existing spec must be re-drafted when reviewer findings are present"
        assert result.status == StepStatus.PASSED, result.error_message


# ---------------------------------------------------------------------------
# Shared feedback helper (extracted so both handlers use one implementation)
# ---------------------------------------------------------------------------


class TestPopStepFeedbackHelper:
    def test_another_steps_feedback_is_left_untouched(self) -> None:
        """Only the executing step's own entry is consumed — siblings must survive."""
        ctx = MagicMock()
        ctx.feedback = {"some_other_step": {"from_step": "review", "findings": {"a": 1}}}

        assert _pop_step_feedback(_step(), ctx) is None
        assert ctx.feedback == {"some_other_step": {"from_step": "review", "findings": {"a": 1}}}

    def test_absent_feedback_returns_none(self) -> None:
        ctx = MagicMock()
        ctx.feedback = {}
        assert _pop_step_feedback(_step(), ctx) is None

    def test_malformed_entry_is_popped_and_treated_as_absent(self) -> None:
        ctx = MagicMock()
        ctx.feedback = {"draft_feature": "not-a-dict"}
        assert _pop_step_feedback(_step(), ctx) is None
        assert "draft_feature" not in ctx.feedback

    def test_findings_not_a_dict_returns_none(self) -> None:
        ctx = MagicMock()
        ctx.feedback = {"draft_feature": {"findings": ["not", "a", "dict"]}}
        assert _pop_step_feedback(_step(), ctx) is None

    def test_well_formed_findings_are_returned(self) -> None:
        ctx = MagicMock()
        ctx.feedback = {"draft_feature": {"from_step": "review", "findings": {"a": 1}}}
        assert _pop_step_feedback(_step(), ctx) == {"a": 1}

    def test_draft_spec_handler_delegate_still_works(self) -> None:
        """The four shipped tests call DraftSpecHandler._pop_feedback directly — keep it alive."""
        ctx = MagicMock()
        ctx.feedback = {"draft_feature": {"from_step": "review", "findings": {"a": 1}}}
        assert DraftSpecHandler._pop_feedback(_step(), ctx) == {"a": 1}


# ---------------------------------------------------------------------------
# Name derivation — tested directly (the FR-1 round-trip invariant lives here)
# ---------------------------------------------------------------------------


class TestDeriveFeatureName:
    """Direct branch tests — this helper carries the whole path-reconciliation contract."""

    @staticmethod
    def _derive(filename: str, tmp_path: Path) -> str | None:
        return DraftFeatureHandler._derive_feature_name(tmp_path / filename)

    def test_valid_name_returns_stem(self, tmp_path: Path) -> None:
        assert self._derive("sell_shares_feature_spec.md", tmp_path) == "sell_shares"

    def test_missing_suffix_returns_none(self, tmp_path: Path) -> None:
        assert self._derive("sell_shares.md", tmp_path) is None

    def test_component_spec_suffix_returns_none(self, tmp_path: Path) -> None:
        """`_spec.md` is the component convention — it must not be accepted here."""
        assert self._derive("sell_shares_spec.md", tmp_path) is None

    def test_bare_suffix_returns_none(self, tmp_path: Path) -> None:
        """Empty derived name: removesuffix would happily return '' — we must not."""
        assert self._derive("_feature_spec.md", tmp_path) is None

    def test_trailing_extension_returns_none(self, tmp_path: Path) -> None:
        """A backup/copy file must not be mistaken for the real spec."""
        assert self._derive("sell_shares_feature_spec.md.bak", tmp_path) is None

    def test_derived_name_round_trips_to_the_original_filename(self, tmp_path: Path) -> None:
        """The invariant FeatureDrafter depends on: name + suffix == the original file."""
        name = self._derive("sell_shares_feature_spec.md", tmp_path)
        assert f"{name}_feature_spec.md" == "sell_shares_feature_spec.md"


# ---------------------------------------------------------------------------
# Lineage, generation config and topology passthrough
# ---------------------------------------------------------------------------


class TestDraftFeatureLineageAndConfig:
    @staticmethod
    def _fake_draft_writing(spec: Path):
        async def fake_draft(_self, *_args, **_kwargs):
            spec.write_text("# Drafted\n", encoding="utf-8")
            return spec

        return fake_draft

    @pytest.mark.asyncio
    @patch("specweaver.core.flow.store.FlowRepository")
    async def test_lineage_event_logged_when_db_configured(
        self, mock_repo_class: MagicMock, tmp_path: Path
    ) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)
        ctx.db = MagicMock()
        ctx.run = ctx.run.model_copy(update={"run_id": "run-42"})

        mock_repo = MagicMock()
        mock_repo.log_artifact_event = AsyncMock()
        mock_repo_class.return_value = mock_repo

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
            new=self._fake_draft_writing(spec),
        ):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.PASSED, result.error_message
        mock_repo.log_artifact_event.assert_called_once_with(
            artifact_id=result.artifact_uuid,
            parent_id=None,
            run_id="run-42",
            event_type="drafted_feature_spec",
            model_id="unknown",
        )

    @pytest.mark.asyncio
    @patch("specweaver.core.flow.store.FlowRepository")
    async def test_generation_config_built_from_context_config(
        self, mock_repo_class: MagicMock, tmp_path: Path
    ) -> None:
        """context.model.config.llm present -> GenerationConfig built; its model reaches lineage."""
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)
        ctx.db = MagicMock()
        ctx.run = ctx.run.model_copy(update={"run_id": "run-7"})
        ctx.model = ctx.model.model_copy(update={"config": MagicMock()})
        ctx.model.config.llm.model = "gemini-3-flash-preview"
        ctx.model.config.llm.temperature = 0.4
        ctx.model.config.llm.max_output_tokens = 2048

        mock_repo = MagicMock()
        mock_repo.log_artifact_event = AsyncMock()
        mock_repo_class.return_value = mock_repo

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
            new=self._fake_draft_writing(spec),
        ):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.PASSED, result.error_message
        assert mock_repo.log_artifact_event.call_args.kwargs["model_id"] == "gemini-3-flash-preview"

    @pytest.mark.asyncio
    @patch("specweaver.core.flow.store.FlowRepository")
    async def test_config_without_llm_attribute_falls_back_to_unknown_model(
        self, mock_repo_class: MagicMock, tmp_path: Path
    ) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)
        ctx.db = MagicMock()

        class _ConfigWithoutLlm:
            pass

        ctx.model = ctx.model.model_copy(update={"config": _ConfigWithoutLlm()})

        mock_repo = MagicMock()
        mock_repo.log_artifact_event = AsyncMock()
        mock_repo_class.return_value = mock_repo

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
            new=self._fake_draft_writing(spec),
        ):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.PASSED, result.error_message
        assert mock_repo.log_artifact_event.call_args.kwargs["model_id"] == "unknown"

    @pytest.mark.asyncio
    async def test_list_topology_is_forwarded(self, tmp_path: Path) -> None:
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)
        topology = [MagicMock()]
        ctx.topology = topology
        seen: dict[str, Any] = {}

        async def fake_draft(_self, _name, _output_dir, **kwargs):
            seen.update(kwargs)
            spec.write_text("# Drafted\n", encoding="utf-8")
            return spec

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft", new=fake_draft
        ):
            await DraftFeatureHandler().execute(_step(), ctx)

        assert seen["topology_contexts"] == topology

    @pytest.mark.asyncio
    async def test_non_list_topology_is_forwarded_as_none(self, tmp_path: Path) -> None:
        """A single TopologyContext (not a list) must not be passed through raw."""
        spec = tmp_path / "greeter_feature_spec.md"
        ctx = _interactive_ctx(tmp_path, spec)
        ctx.topology = MagicMock()
        seen: dict[str, Any] = {}

        async def fake_draft(_self, _name, _output_dir, **kwargs):
            seen.update(kwargs)
            spec.write_text("# Drafted\n", encoding="utf-8")
            return spec

        with patch(
            "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft", new=fake_draft
        ):
            await DraftFeatureHandler().execute(_step(), ctx)

        assert seen["topology_contexts"] is None

    @pytest.mark.asyncio
    async def test_reviewer_findings_are_injected_into_the_prompt(self, tmp_path: Path) -> None:
        """The re-draft must actually carry the findings, not just re-run."""
        spec = tmp_path / "greeter_feature_spec.md"
        spec.write_text("# Greeter\n", encoding="utf-8")
        ctx = _interactive_ctx(tmp_path, spec)
        ctx.feedback = {"draft_feature": {"from_step": "review", "findings": {"issue": "vague"}}}
        fake_prompt = MagicMock()

        async def fake_draft(_self, *_args, **_kwargs):
            return spec

        with (
            patch(
                "specweaver.core.flow.handlers.base._build_base_prompt",
                new=AsyncMock(return_value=fake_prompt),
            ),
            patch(
                "specweaver.workflows.drafting.feature_drafter.FeatureDrafter.draft",
                new=fake_draft,
            ),
        ):
            result = await DraftFeatureHandler().execute(_step(), ctx)

        assert result.status == StepStatus.PASSED, result.error_message
        labels = [c.args[1] for c in fake_prompt.add_context.call_args_list if len(c.args) > 1]
        assert "reviewer_findings" in labels
