from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.assurance.validation.models import RuleResult
from specweaver.assurance.validation.models import Status as RuleStatus
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.generation import GenerateCodeHandler, GenerateTestsHandler
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.handlers.review import ReviewCodeHandler, ReviewSpecHandler
from specweaver.core.flow.handlers.validation import ValidateCodeHandler, ValidateTestsHandler


@pytest.fixture
def run_context(tmp_path: Path) -> RunContext:
    ctx = RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "test_spec.md",
        output_dir=tmp_path / "out",
    )
    ctx.output_dir.mkdir(parents=True, exist_ok=True)
    ctx.spec_path.touch()
    return ctx


@pytest.fixture
def pipeline_step() -> PipelineStep:
    return PipelineStep(name="test_step", action=StepAction.VALIDATE, target=StepTarget.FEATURE)


@pytest.mark.asyncio
async def test_validate_code_handler_empty_dir(
    run_context: RunContext, pipeline_step: PipelineStep
) -> None:
    """ValidateCodeHandler gracefully fails when output directory has no Python files."""
    handler = ValidateCodeHandler()
    result = await handler.execute(pipeline_step, run_context)
    assert result.status == StepStatus.ERROR
    assert "No code file found" in (result.error_message or "")


@pytest.mark.asyncio
async def test_validate_code_handler_success_output(
    run_context: RunContext, pipeline_step: PipelineStep
) -> None:
    """ValidateCodeHandler constructs proper output payloads when validation rules execute."""
    (run_context.output_dir / "foo.py").touch()

    handler = ValidateCodeHandler()

    with patch.object(handler, "_run_validation") as mock_run:
        mock_run.return_value = [
            RuleResult(
                rule_id="r1",
                rule_name="rule1",
                status=RuleStatus.PASS,
                message="OK",
                line=1,
                file="foo.py",
            ),
            RuleResult(
                rule_id="r2",
                rule_name="rule2",
                status=RuleStatus.FAIL,
                message="Bad",
                line=2,
                file="foo.py",
            ),
        ]
        result = await handler.execute(pipeline_step, run_context)

        assert result.status == StepStatus.FAILED
        assert result.output["total"] == 2
        assert result.output["passed"] == 1
        assert result.output["failed"] == 1


@pytest.mark.asyncio
async def test_generate_handlers_exception_wrapper(
    run_context: RunContext, pipeline_step: PipelineStep
) -> None:
    """GenerateCodeHandler and GenerateTestsHandler trap LLM generation faults."""
    run_context.llm = AsyncMock()

    code_handler = GenerateCodeHandler()
    test_handler = GenerateTestsHandler()

    with patch(
        "specweaver.workflows.implementation.generator.Generator.generate_code",
        side_effect=ValueError("LLM Crash"),
    ):
        result = await code_handler.execute(pipeline_step, run_context)
        assert result.status == StepStatus.ERROR
        assert "LLM Crash" in (result.error_message or "")

    with patch(
        "specweaver.workflows.implementation.generator.Generator.generate_tests",
        side_effect=ValueError("LLM Crash Tests"),
    ):
        result2 = await test_handler.execute(pipeline_step, run_context)
        assert result2.status == StepStatus.ERROR
        assert "LLM Crash Tests" in (result2.error_message or "")


@pytest.mark.asyncio
async def test_validate_tests_handler_lazy_atom(
    run_context: RunContext, pipeline_step: PipelineStep
) -> None:
    """ValidateTestsHandler can instantiate its atom."""
    handler = ValidateTestsHandler()
    atom = handler._get_atom(run_context)
    from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

    assert isinstance(atom, QARunnerAtom)


@pytest.mark.asyncio
async def test_lint_fix_handler_missing_code(
    run_context: RunContext, pipeline_step: PipelineStep
) -> None:
    """LintFixHandler safely aborts reflection if code files vanish."""
    run_context.llm = AsyncMock()
    handler = LintFixHandler()

    with patch.object(handler, "_get_atom") as mock_get_atom:
        mock_atom = MagicMock()
        mock_get_atom.return_value = mock_atom

        mock_atom.run.side_effect = [
            # Initial lint returns an error
            MagicMock(exports={"error_count": 1, "errors": [{"line": 1}]}),
            # Auto-fix run
            MagicMock(),
            # Post-auto-fix lint STILL returns error
            MagicMock(exports={"error_count": 1, "errors": [{"line": 1}]}),
        ]

        # We ensure output dir is empty so _find_code_files returns []
        result = await handler.execute(pipeline_step, run_context)
        assert result.status == StepStatus.FAILED
        assert "No code files found" in (result.error_message or "")


@pytest.mark.asyncio
async def test_lint_fix_handler_ast_fences(tmp_path: Path, run_context: RunContext) -> None:
    """LintFixHandler strips markdown fences correctly."""
    handler = LintFixHandler()
    llm = AsyncMock()
    llm.generate.return_value = MagicMock(text="```python\nprint('fixed')\n```")

    code_path = tmp_path / "target.py"
    code_path.touch()

    await handler._llm_fix(llm, code_path, [{"line": 1}], context=run_context)

    fixed = code_path.read_text(encoding="utf-8")
    assert "print('fixed')" in fixed
    assert "```" not in fixed


@pytest.mark.asyncio
async def test_review_handlers_execution(
    run_context: RunContext, pipeline_step: PipelineStep
) -> None:
    """ReviewSpecHandler and ReviewCodeHandler execute their core LLM logic without crashing."""
    run_context.llm = AsyncMock()
    (run_context.output_dir / "foo.py").touch()

    spec_handler = ReviewSpecHandler()
    code_handler = ReviewCodeHandler()

    mock_review_result = MagicMock()
    mock_review_result.verdict.value = "accepted"
    mock_review_result.findings = []
    mock_review_result.summary = "Acceptable"
    mock_review_result.raw_response = "Looks good. No issues found."

    with patch(
        "specweaver.workflows.review.reviewer.Reviewer.review_spec", return_value=mock_review_result
    ):
        res1 = await spec_handler.execute(pipeline_step, run_context)
        assert res1.status == StepStatus.PASSED

    with patch(
        "specweaver.workflows.review.reviewer.Reviewer.review_code", return_value=mock_review_result
    ):
        res2 = await code_handler.execute(pipeline_step, run_context)
        assert res2.status == StepStatus.PASSED
