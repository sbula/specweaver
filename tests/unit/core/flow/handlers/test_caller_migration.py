# mypy: ignore-errors
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from specweaver.core.flow.handlers._profiles import ARBITER, FULL, INTERACTIVE, MINIMAL
from specweaver.core.flow.handlers.base import RunContext


@pytest.fixture
def run_context(tmp_path):
    from unittest.mock import MagicMock

    from specweaver.infrastructure.llm.models import ProjectMetadata, PromptSafeConfig

    db = MagicMock()
    metadata = ProjectMetadata(
        project_name="test",
        archetype="generic",
        language_target="python",
        date_iso="2026-05-13",
        safe_config=PromptSafeConfig(llm_provider="fake", llm_model="fake"),
    )

    spec_path = tmp_path / "spec.md"
    spec_path.write_text("content", encoding="utf-8")

    project_path = tmp_path

    return RunContext(
        project_path=project_path,
        spec_path=spec_path,
        constitution="",
        standards="",
        db=db,
        project_metadata=metadata,
        parsers={},
    )


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.base._build_base_prompt")
@patch("specweaver.workflows.drafting.drafter.Drafter")
async def test_draft_handler_uses_interactive_profile(mock_drafter_class, mock_build, run_context):
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.draft import DraftSpecHandler

    mock_build.return_value = AsyncMock()
    mock_drafter = mock_drafter_class.return_value
    mock_drafter.draft = AsyncMock(return_value="/tmp/spec.md")

    handler = DraftSpecHandler()
    run_context.llm = AsyncMock()
    run_context.context_provider = AsyncMock()

    if run_context.spec_path.exists():
        run_context.spec_path.unlink()

    step = PipelineStep(
        name="draft", module="feature", action="draft", target="spec", handler="DraftSpecHandler"
    )
    await handler.execute(step, run_context)

    # M1 verification
    mock_build.assert_called_once()
    _, kwargs = mock_build.call_args
    assert kwargs.get("profile") == INTERACTIVE


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.base._build_base_prompt")
@patch("specweaver.workflows.implementation.generator.Generator")
async def test_generate_code_uses_full_profile(mock_generator_class, mock_build, run_context):
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.generation import GenerateCodeHandler

    mock_build.return_value = AsyncMock()
    mock_generator = mock_generator_class.return_value
    mock_generator.generate = AsyncMock()

    handler = GenerateCodeHandler()
    run_context.llm = AsyncMock()
    run_context.context_provider = AsyncMock()

    step = PipelineStep(
        name="gen",
        module="feature",
        action="generate",
        target="code",
        handler="GenerateCodeHandler",
        params={"output_dir": "/tmp/out"},
    )
    await handler.execute(step, run_context)

    # M2 verification
    mock_build.assert_called_once()
    _, kwargs = mock_build.call_args
    assert kwargs.get("profile") == FULL


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.base._build_base_prompt")
@patch("specweaver.workflows.implementation.generator.Generator")
async def test_generate_tests_uses_full_profile(mock_generator_class, mock_build, run_context):
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.generation import GenerateTestsHandler

    mock_build.return_value = AsyncMock()
    mock_generator = mock_generator_class.return_value
    mock_generator.generate = AsyncMock()

    handler = GenerateTestsHandler()
    run_context.llm = AsyncMock()
    run_context.context_provider = AsyncMock()

    step = PipelineStep(
        name="gen",
        module="feature",
        action="generate",
        target="tests",
        handler="GenerateTestsHandler",
        params={"output_dir": "/tmp/out"},
    )
    await handler.execute(step, run_context)

    # M3 verification
    mock_build.assert_called_once()
    _, kwargs = mock_build.call_args
    assert kwargs.get("profile") == FULL


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.base._build_base_prompt")
@patch("specweaver.workflows.planning.planner.Planner")
async def test_plan_spec_uses_full_profile(mock_planner_class, mock_build, run_context):
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.generation import PlanSpecHandler

    mock_build.return_value = AsyncMock()
    mock_planner = mock_planner_class.return_value
    mock_planner.generate_plan = AsyncMock()

    handler = PlanSpecHandler()
    run_context.llm = AsyncMock()
    run_context.context_provider = AsyncMock()

    step = PipelineStep(
        name="plan", module="feature", action="plan", target="spec", handler="PlanSpecHandler"
    )
    await handler.execute(step, run_context)

    # M4 verification
    mock_build.assert_called_once()
    _, kwargs = mock_build.call_args
    assert kwargs.get("profile") == FULL


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.base._build_base_prompt")
@patch("specweaver.workflows.review.reviewer.Reviewer")
async def test_review_spec_uses_full_profile(mock_reviewer_class, mock_build, run_context):
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.review import ReviewSpecHandler

    mock_build.return_value = AsyncMock()
    mock_reviewer = mock_reviewer_class.return_value
    mock_reviewer.review = AsyncMock()

    handler = ReviewSpecHandler()
    run_context.llm = AsyncMock()
    run_context.context_provider = AsyncMock()

    step = PipelineStep(
        name="rev", module="feature", action="review", target="spec", handler="ReviewSpecHandler"
    )
    await handler.execute(step, run_context)

    # M5 verification
    mock_build.assert_called_once()
    _, kwargs = mock_build.call_args
    assert kwargs.get("profile") == FULL


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.base._build_base_prompt")
@patch("specweaver.workflows.review.reviewer.Reviewer")
async def test_review_code_uses_full_profile(
    mock_reviewer_class, mock_build, run_context, tmp_path
):
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.review import ReviewCodeHandler

    mock_build.return_value = AsyncMock()
    mock_reviewer = mock_reviewer_class.return_value
    mock_reviewer.review = AsyncMock()

    handler = ReviewCodeHandler()
    run_context.llm = AsyncMock()
    run_context.context_provider = AsyncMock()

    code_file = tmp_path / "code.py"
    code_file.write_text("print('hello')", encoding="utf-8")

    step = PipelineStep(
        name="rev",
        module="feature",
        action="review",
        target="code",
        handler="ReviewCodeHandler",
        params={"target_path": str(code_file)},
    )

    await handler.execute(step, run_context)

    # M6 verification
    mock_build.assert_called_once()
    _, kwargs = mock_build.call_args
    assert kwargs.get("profile") == FULL


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.base._build_base_prompt")
async def test_arbitrate_verdict_uses_arbiter_profile(mock_build, run_context, tmp_path):
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.arbiter import ArbitrateVerdictHandler

    mock_build.return_value = AsyncMock()
    mock_build.return_value.build.return_value = "fake prompt"

    handler = ArbitrateVerdictHandler()
    run_context.llm = AsyncMock()
    run_context.llm.generate.return_value = '{"verdict": "CODE_BUG", "spec_clause": "test", "coding_feedback": "test", "scenario_feedback": "test"}'
    # INT-US-24 FR-2: failure evidence required to reach prompt building.
    run_context.feedback["scenario_test_failures"] = {
        "passed": 0,
        "failed": 1,
        "errors": 0,
        "total": 1,
        "failures": [{"nodeid": "t.py::t", "message": "boom", "stacktrace": "tb"}],
    }

    step = PipelineStep(
        name="arb",
        module="feature",
        action="arbitrate",
        target="verdict",
        handler="ArbitrateVerdictHandler",
    )

    await handler.execute(step, run_context)

    # A1 verification
    mock_build.assert_called_once()
    _, kwargs = mock_build.call_args
    assert kwargs.get("profile") == ARBITER


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.base._build_base_prompt")
async def test_decompose_feature_uses_minimal_profile(mock_build, run_context, tmp_path):
    from unittest.mock import MagicMock

    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.decompose import DecomposeFeatureHandler

    mock_build.return_value = AsyncMock()
    mock_build.return_value.build.return_value = "fake prompt"

    with patch(
        "specweaver.core.flow.handlers.decompose.FeatureDecomposer"
    ) as mock_decomposer_class:
        mock_decomposer = mock_decomposer_class.return_value
        mock_plan = MagicMock()
        mock_plan.coverage_score = 1.0
        mock_decomposer.decompose = AsyncMock(return_value=mock_plan)

        handler = DecomposeFeatureHandler()
        run_context.llm = AsyncMock()

        step = PipelineStep(
            name="dec",
            module="feature",
            action="decompose",
            target="feature",
            handler="DecomposeFeatureHandler",
        )

        await handler.execute(step, run_context)

        # D1 verification
        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        assert kwargs.get("profile") == MINIMAL
