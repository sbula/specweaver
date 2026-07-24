# mypy: ignore-errors
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.arbiter import (
    ArbitrateResult,
    ArbitrateVerdict,
    ArbitrateVerdictHandler,
    _guard_coding_feedback,
)


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


def _evidence(**overrides):
    """Real QA export shape (INT-US-24 FR-2) — what ValidateTestsHandler publishes."""
    payload = {
        "passed": 3,
        "failed": 2,
        "errors": 0,
        "total": 5,
        "failures": [
            {"nodeid": "test_x.py::test_a", "message": "error trace", "stacktrace": "tb-frames"},
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def run_context():
    ctx = MagicMock()
    ctx.run_id = "test_run"
    ctx.feedback = {"scenario_test_failures": _evidence()}
    ctx.spec_path.exists.return_value = True
    ctx.spec_path.read_text.return_value = "Spec data"
    ctx.project_path = "/mock/path"
    ctx.llm = AsyncMock()
    return ctx


class TestArbitrateVerdictHandler:
    @pytest.mark.asyncio
    @patch("specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter")
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
        # Consume-on-verdict: code_bug is terminal → evidence popped.
        assert "scenario_test_failures" not in run_context.feedback
        # The REAL failure evidence reached the filter (message + stacktrace).
        raw_seen = mock_create_filter.return_value.filter.call_args[0][0]
        assert "error trace" in raw_seen
        assert "tb-frames" in raw_seen

    @pytest.mark.asyncio
    @patch("specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter")
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
    @patch("specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter")
    async def test_spec_ambiguity_returns_waiting_for_input(self, mock_create_filter, run_context):
        mock_create_filter.return_value.filter.return_value = "Filtered trace"
        run_context.llm.generate.return_value = (
            '{"verdict": "spec_ambiguity", "spec_clause": "FR-2"}'
        )

        handler = ArbitrateVerdictHandler()
        step = PipelineStep(name="test", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)

        result = await handler.execute(step, run_context)
        assert result.status == StepStatus.WAITING_FOR_INPUT
        assert "Ambiguity detected on FR-2" in result.error_message
        # Consume-on-verdict: spec_ambiguity PARKS — evidence must be RETAINED
        # so `sw run --resume` can re-arbitrate instead of ERRORing on absence.
        assert "scenario_test_failures" in run_context.feedback


# ---------------------------------------------------------------------------
# INT-US-24 SF-01 T4 (FR-2 consumer): evidence contract — green short-circuit,
# loud absence, total==0 guard, consume-on-verdict, hostile shapes.
# ---------------------------------------------------------------------------


def _arb_step() -> PipelineStep:
    return PipelineStep(name="arbitrate_verdict", action=StepAction.ARBITRATE, target=StepTarget.VERDICT)


class TestArbitrateEvidenceContract:
    @pytest.mark.asyncio
    async def test_green_evidence_passes_with_zero_llm_calls(self, run_context):
        # [Happy] total>0 ∧ failed==0 ∧ errors==0 → PASSED, no arbitration cost.
        run_context.feedback = {
            "scenario_test_failures": _evidence(passed=5, failed=0, errors=0, failures=[])
        }
        result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)

        assert result.status == StepStatus.PASSED
        assert result.output["verdict"] == "no_failures"
        run_context.llm.generate.assert_not_called()
        # no_failures is terminal → popped.
        assert "scenario_test_failures" not in run_context.feedback

    @pytest.mark.asyncio
    async def test_green_short_circuit_works_without_llm(self, run_context):
        # [Boundary] a green verdict needs no LLM at all — must not trip the
        # "LLM not configured" guard.
        run_context.llm = None
        run_context.feedback = {
            "scenario_test_failures": _evidence(passed=5, failed=0, errors=0, failures=[])
        }
        result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)
        assert result.status == StepStatus.PASSED

    @pytest.mark.asyncio
    async def test_absent_evidence_is_a_loud_wiring_error(self, run_context):
        # [Graceful degradation] no evidence key → the wire is broken; never
        # silently pass, never crash.
        run_context.feedback = {}
        result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)

        assert result.status == StepStatus.ERROR
        assert "scenario" in result.error_message.lower()
        assert "evidence" in result.error_message.lower()
        run_context.llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_errors_only_evidence_still_arbitrates(self, run_context):
        # [Boundary/E1] failed==0 but errors>0 (e.g. import crash in the
        # generated test file) is NOT green — must arbitrate.
        run_context.llm.generate.return_value = (
            '{"verdict": "scenario_error", "scenario_feedback": "Broken import"}'
        )
        run_context.feedback = {
            "scenario_test_failures": _evidence(passed=0, failed=0, errors=3, failures=[])
        }
        with patch(
            "specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter"
        ) as mock_filter:
            mock_filter.return_value.filter.return_value = "Filtered"
            result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)

        assert result.status == StepStatus.FAILED
        run_context.llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_zero_total_fails_loud_without_llm(self, run_context):
        # [Boundary/E2] total==0 leaked through the continue-gate → the
        # arbiter is the last line: FAILED, never a green completion.
        run_context.feedback = {
            "scenario_test_failures": _evidence(passed=0, failed=0, errors=0, total=0, failures=[])
        }
        result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)

        assert result.status == StepStatus.FAILED
        assert "no scenario tests" in result.error_message.lower()
        run_context.llm.generate.assert_not_called()
        # Not a terminal verdict branch → retained (loop re-publication overwrites).
        assert "scenario_test_failures" in run_context.feedback

    @pytest.mark.asyncio
    async def test_unparseable_llm_verdict_retains_evidence(self, run_context):
        # [Graceful degradation] ERROR (bad LLM JSON) → evidence retained for
        # the retry.
        run_context.llm.generate.return_value = "not json at all"
        with patch(
            "specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter"
        ) as mock_filter:
            mock_filter.return_value.filter.return_value = "Filtered"
            result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)

        assert result.status == StepStatus.ERROR
        assert "scenario_test_failures" in run_context.feedback

    @pytest.mark.asyncio
    async def test_empty_dict_evidence_fails_as_zero_total(self, run_context):
        # [Boundary] G-b: the end-to-end timeout shape — evidence is {} (no
        # counts at all) → treated as total==0: FAILED loud, no LLM, no crash.
        run_context.feedback = {"scenario_test_failures": {}}
        result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)

        assert result.status == StepStatus.FAILED
        assert "no scenario tests" in result.error_message.lower()
        run_context.llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_string_counts_error_as_malformed(self, run_context):
        # [Hostile] G-c: non-int counts (e.g. total: "5") → malformed ERROR.
        run_context.feedback = {"scenario_test_failures": _evidence(total="5")}
        result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)

        assert result.status == StepStatus.ERROR
        assert "malformed" in result.error_message.lower()
        run_context.llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_list_failures_error_as_malformed(self, run_context):
        # [Hostile] G-c: failures not a list → malformed ERROR.
        run_context.feedback = {"scenario_test_failures": _evidence(failures="notalist")}
        result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)

        assert result.status == StepStatus.ERROR
        assert "malformed" in result.error_message.lower()
        run_context.llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_dict_evidence_errors_cleanly(self, run_context):
        # [Hostile] garbage under the reserved key → ERROR, no crash.
        run_context.feedback = {"scenario_test_failures": "garbage-string"}
        result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)

        assert result.status == StepStatus.ERROR
        assert "malformed" in result.error_message.lower()
        run_context.llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_dict_failure_entries_error_cleanly(self, run_context):
        # [Hostile] failures list with non-dict entries → ERROR, no crash.
        run_context.feedback = {
            "scenario_test_failures": _evidence(failures=["not-a-dict", 42])
        }
        result = await ArbitrateVerdictHandler().execute(_arb_step(), run_context)

        assert result.status == StepStatus.ERROR
        assert "malformed" in result.error_message.lower()
        run_context.llm.generate.assert_not_called()
