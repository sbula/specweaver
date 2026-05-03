from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.arbiter import ArbitrateVerdictHandler
from specweaver.core.flow.handlers.base import RunContext


@pytest.fixture
def run_context():
    ctx = MagicMock(spec=RunContext)
    ctx.run_id = "test_run_123"
    ctx.spec_path = MagicMock()
    ctx.spec_path.stem = "auth_spec.md"
    ctx.project_path = "/mock/project"
    ctx.feedback = {
        "run_scenario_tests": {
            "output": {"results": [{"status": "FAIL", "message": "AssertionError: 1 != 2"}]}
        }
    }

    ctx.pipeline_runner = MagicMock()
    ctx.pipeline_runner._context = ctx
    ctx.pipeline_runner._registry = MagicMock()
    ctx.pipeline_runner._store = MagicMock()
    ctx.pipeline_runner._on_event = MagicMock()
    return ctx


class TestArbiterIntegrationFlow:
    @pytest.mark.asyncio
    @patch("specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter")
    async def test_end_to_end_arbiter_verdict(self, mock_create_filter, run_context):
        # Setup mocks
        mock_filter = MagicMock()
        mock_filter.filter.return_value = "Cleaned assertion text"
        mock_create_filter.return_value = mock_filter

        run_context.llm = AsyncMock()
        # Mock LLM verdict
        run_context.llm.generate.return_value = '{"verdict": "code_bug", "coding_feedback": "The implementation drifted.", "scenario_feedback": ""}'
        run_context.spec_path.exists.return_value = True
        run_context.spec_path.read_text.return_value = "## Spec Content"

        handler = ArbitrateVerdictHandler()
        step = PipelineStep(name="test_arb", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)

        # Execute Handler
        result = await handler.execute(step, run_context)

        # Assert status is intercepted correctly
        assert result.status == StepStatus.FAILED
        assert "The implementation drifted" in result.error_message

        # Check context injection mapping
        assert "generate_code" in run_context.feedback
        findings = run_context.feedback["generate_code"]["findings"]
        assert findings["verdict"] == "code_bug"
        assert len(findings["results"]) == 1
        assert "The implementation drifted" in findings["results"][0]["message"]

    @pytest.mark.asyncio
    @patch("specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter")
    async def test_nfr8_no_scenario_vocab_in_coding_feedback(self, mock_create_filter, run_context):
        mock_create_filter.return_value.filter.return_value = "Filtered trace"
        run_context.llm = AsyncMock()
        # LLM tries to leak scenario vocabulary
        run_context.llm.generate.return_value = '{"verdict": "code_bug", "coding_feedback": "The scenario test failed on Pytest parametrized inputs.", "scenario_feedback": ""}'
        run_context.spec_path.exists.return_value = True
        run_context.spec_path.read_text.return_value = "## Spec Content"

        handler = ArbitrateVerdictHandler()
        step = PipelineStep(name="test_arb", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)
        await handler.execute(step, run_context)

        feedback = run_context.feedback["generate_code"]["findings"]["results"][0]["message"]
        # Vocabulary guard should rewrite it
        assert "behave according to the behavioral constraints" in feedback
        assert "pytest" not in feedback.lower()

    @pytest.mark.asyncio
    @patch("specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter")
    async def test_scenario_error_feedback_reaches_generate_scenarios_handler(
        self, mock_create_filter, run_context
    ):
        mock_create_filter.return_value.filter.return_value = "Filtered trace"
        run_context.llm = AsyncMock()
        run_context.llm.generate.return_value = '{"verdict": "scenario_error", "coding_feedback": "", "scenario_feedback": "Check FR-1 test."}'
        run_context.spec_path.exists.return_value = True
        run_context.spec_path.read_text.return_value = "## Spec Content"

        handler = ArbitrateVerdictHandler()
        step = PipelineStep(name="test_arb", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)
        result = await handler.execute(step, run_context)

        assert result.status == StepStatus.FAILED
        assert "generate_scenarios" in run_context.feedback
        assert (
            "Check FR-1 test."
            in run_context.feedback["generate_scenarios"]["findings"]["results"][0]["message"]
        )

    @pytest.mark.asyncio
    @patch("specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter")
    async def test_gracefully_handles_malformed_json(self, mock_create_filter, run_context):
        mock_create_filter.return_value.filter.return_value = "Filtered trace"
        run_context.llm = AsyncMock()
        run_context.llm.generate.return_value = '{"verdict": "code_bug", missing quotes}'
        run_context.spec_path.exists.return_value = True
        run_context.spec_path.read_text.return_value = "## Spec Content"

        handler = ArbitrateVerdictHandler()
        step = PipelineStep(name="test_arb", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)
        result = await handler.execute(step, run_context)

        assert result.status == StepStatus.ERROR

    @pytest.mark.asyncio
    @patch("specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter")
    async def test_spec_ambiguity_parks_run(self, mock_create_filter, run_context):
        mock_create_filter.return_value.filter.return_value = "Filtered trace"
        run_context.llm = AsyncMock()
        run_context.llm.generate.return_value = (
            '{"verdict": "spec_ambiguity", "spec_clause": "FR-99"}'
        )
        run_context.spec_path.exists.return_value = True
        run_context.spec_path.read_text.return_value = "## Spec Content"

        handler = ArbitrateVerdictHandler()
        step = PipelineStep(name="test_arb", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)
        result = await handler.execute(step, run_context)

        assert result.status == StepStatus.WAITING_FOR_INPUT
        assert "Ambiguity detected on FR-99" in result.error_message
