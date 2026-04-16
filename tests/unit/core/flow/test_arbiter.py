from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow._arbiter import (
    ArbitrateResult,
    ArbitrateVerdict,
    ArbitrateVerdictHandler,
    _guard_coding_feedback,
)
from specweaver.core.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.state import StepStatus


class TestArbitrateVerdict:
    def test_all_verdict_values(self):
        vals = [v.value for v in ArbitrateVerdict]
        assert "code_bug" in vals
        assert "scenario_error" in vals
        assert "spec_ambiguity" in vals


class TestArbitrateResult:
    def test_model_validation(self):
        data = {
            "verdict": "code_bug",
            "reasoning": "Reason",
            "spec_clause": "FR-1",
            "coding_feedback": "Code invalid",
            "scenario_feedback": "Test invalid",
        }
        res = ArbitrateResult(**data)
        assert res.verdict == ArbitrateVerdict.CODE_BUG
        assert res.reasoning == "Reason"


class TestVocabularyGuard:
    def test_clean_feedback_unchanged(self):
        val = "Function x does not return integer."
        assert _guard_coding_feedback(val) == val

    def test_leaked_scenario_term_triggers_fallback(self):
        val = "The scenario test failed"
        assert "behave according to the behavioral constraints" in _guard_coding_feedback(val)

    def test_case_insensitive_detection(self):
        val = "Pytest parametrized variables are missing"
        assert "behave according to the behavioral constraints" in _guard_coding_feedback(val)


@pytest.fixture
def run_context():
    ctx = MagicMock()
    ctx.run_id = "test_run"
    ctx.feedback = {
        "run_scenario_tests": {
            "output": {"results": [{"status": "FAIL", "message": "error trace"}]}
        }
    }
    ctx.spec_path.exists.return_value = True
    ctx.spec_path.read_text.return_value = "Spec data"
    ctx.project_path = "/mock/path"
    ctx.llm = AsyncMock()
    return ctx


class TestArbitrateVerdictHandler:
    @pytest.mark.asyncio
    @patch(
        "specweaver.core.loom.commons.language.stack_trace_filter_factory.create_stack_trace_filter"
    )
    async def test_code_bug_writes_to_generate_code_feedback(self, mock_create_filter, run_context):
        mock_create_filter.return_value.filter.return_value = "Filtered trace"

        run_context.llm.generate.return_value = (
            '{"verdict": "code_bug", "reasoning": "bad code", "coding_feedback": "Check FR-1"}'
        )

        handler = ArbitrateVerdictHandler()
        step = PipelineStep(name="test", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)

        result = await handler.execute(step, run_context)

        assert result.status == StepStatus.FAILED
        assert (
            run_context.feedback["generate_code"]["findings"]["results"][0]["message"]
            == "Check FR-1"
        )

    @pytest.mark.asyncio
    @patch(
        "specweaver.core.loom.commons.language.stack_trace_filter_factory.create_stack_trace_filter"
    )
    async def test_scenario_error_writes_to_generate_scenarios_feedback(
        self, mock_create_filter, run_context
    ):
        mock_create_filter.return_value.filter.return_value = "Filtered trace"
        run_context.llm.generate.return_value = '{"verdict": "scenario_error", "reasoning": "bad code", "scenario_feedback": "Check FR-1"}'

        handler = ArbitrateVerdictHandler()
        step = PipelineStep(name="test", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)
        result = await handler.execute(step, run_context)

        assert result.status == StepStatus.FAILED
        assert (
            run_context.feedback["generate_scenarios"]["findings"]["results"][0]["message"]
            == "Check FR-1"
        )

    @pytest.mark.asyncio
    async def test_no_llm_returns_error(self, run_context):
        run_context.llm = None
        handler = ArbitrateVerdictHandler()
        step = PipelineStep(name="test", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)
        result = await handler.execute(step, run_context)

        assert result.status == StepStatus.ERROR
        assert "LLM not configured" in result.error_message

    @pytest.mark.asyncio
    @patch(
        "specweaver.core.loom.commons.language.stack_trace_filter_factory.create_stack_trace_filter"
    )
    async def test_spec_ambiguity_returns_waiting_for_input(self, mock_create_filter, run_context):
        run_context.llm.generate.return_value = (
            '{"verdict": "spec_ambiguity", "spec_clause": "FR-2"}'
        )

        handler = ArbitrateVerdictHandler()
        step = PipelineStep(name="test", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)

        result = await handler.execute(step, run_context)
        assert result.status == StepStatus.WAITING_FOR_INPUT
        assert "Ambiguity detected on FR-2" in result.error_message
