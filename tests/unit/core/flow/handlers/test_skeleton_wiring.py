from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.generation import GenerateCodeHandler
from specweaver.core.flow.handlers.review import ReviewCodeHandler


@patch("specweaver.workflows.implementation.generator.Generator")
@patch("specweaver.core.flow.handlers.context_assembler.evaluate_and_fetch_skeleton_context")
@patch("specweaver.core.flow.handlers.generation.evaluate_and_fetch_mcp_context")
@pytest.mark.asyncio
async def test_generate_code_handler_skeleton_wiring(
    mock_auth_mcp, mock_eval_skel, mock_generator_class, tmp_path: Path
) -> None:
    """Story 9: GenerateCodeHandler properly proxies dictionary seamlessly into Generator."""
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "foo.md")
    ctx.api_contract_paths = ["c:/fake/contract.py"]
    ctx.llm = MagicMock()

    step = PipelineStep(name="test", action="generate", target="code")
    handler = GenerateCodeHandler()

    mock_auth_mcp.return_value = None
    mock_eval_skel.return_value = {"c:/fake/contract.py": "def fake(): pass"}

    mock_generator_instance = mock_generator_class.return_value
    mock_generator_instance.generate_code = AsyncMock(return_value=tmp_path / "foo.py")

    with patch(
        "specweaver.core.flow.handlers.generation.asyncio.to_thread", new_callable=AsyncMock
    ) as mock_thread:
        mock_thread.return_value = {"c:/fake/contract.py": "def fake(): pass"}
        res = await handler.execute(step, ctx)

        assert res.status.value == "passed"
        mock_thread.assert_called_once_with(mock_eval_skel, ctx, ["c:/fake/contract.py"])

        mock_generator_instance.generate_code.assert_called_once()
        kwargs = mock_generator_instance.generate_code.call_args.kwargs
        assert "skeleton_files" in kwargs
        assert kwargs["skeleton_files"] == {"c:/fake/contract.py": "def fake(): pass"}


@patch("specweaver.workflows.review.reviewer.Reviewer")
@patch("specweaver.core.flow.handlers.context_assembler.evaluate_and_fetch_skeleton_context")
@patch("specweaver.core.flow.handlers.review.evaluate_and_fetch_mcp_context")
@pytest.mark.asyncio
async def test_review_code_handler_skeleton_wiring(
    mock_auth_mcp, mock_eval_skel, mock_reviewer_class, tmp_path: Path
) -> None:
    """Story 10 & 10b: ReviewCodeHandler correctly buffers context and tests cross-platform resolution mapping."""
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "foo_spec.md")

    # Simulate output dir having the code file
    ctx.output_dir = tmp_path
    code_path = tmp_path / "foo.py"
    code_path.touch()

    ctx.api_contract_paths = ["c:/fake/contract.py"]
    ctx.llm = MagicMock()

    step = PipelineStep(name="test", action="review", target="code")
    handler = ReviewCodeHandler()

    mock_auth_mcp.return_value = None
    mock_eval_skel.return_value = {
        "c:/fake/contract.py": "def fake(): pass",
        str(code_path): "def code(): pass",
    }

    mock_reviewer_instance = mock_reviewer_class.return_value
    mock_mock_result = MagicMock()
    mock_mock_result.verdict.value = "accepted"
    mock_mock_result.findings = []
    mock_mock_result.raw_response = "raw response payload text"
    mock_reviewer_instance.review_code = AsyncMock(return_value=mock_mock_result)

    with patch(
        "specweaver.core.flow.handlers.review.asyncio.to_thread", new_callable=AsyncMock
    ) as mock_thread:
        mock_thread.return_value = {
            "c:/fake/contract.py": "def fake(): pass",
            str(code_path): "def code(): pass",
        }
        res = await handler.execute(step, ctx)

        assert res.status.value == "passed"
        mock_thread.assert_called_once()

        # Check target assembly appended the code_path implicitly
        assembly_targets = mock_thread.call_args.args[2]
        assert "c:/fake/contract.py" in assembly_targets
        assert str(code_path) in assembly_targets

        mock_reviewer_instance.review_code.assert_called_once()
        kwargs = mock_reviewer_instance.review_code.call_args.kwargs
        assert "skeleton_files" in kwargs
        assert kwargs["skeleton_files"] == {
            "c:/fake/contract.py": "def fake(): pass",
            str(code_path): "def code(): pass",
        }


@patch("specweaver.workflows.review.reviewer.Reviewer")
@patch("specweaver.core.flow.handlers.context_assembler.CodeStructureAtom")
@patch("specweaver.core.flow.handlers.review.evaluate_and_fetch_mcp_context")
@pytest.mark.asyncio
async def test_review_e2e_fallback_protection(
    mock_auth_mcp, mock_atom_class, mock_reviewer_class, tmp_path: Path
) -> None:
    """Story 12: Pipeline Completely suppresses binary faults and falls back downstream natively."""
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "foo.md")
    ctx.api_contract_paths = ["c:/fake/contract.py"]
    ctx.llm = MagicMock()

    step = PipelineStep(name="test", action="review", target="spec")
    from specweaver.core.flow.handlers.review import ReviewSpecHandler

    handler = ReviewSpecHandler()

    mock_auth_mcp.return_value = None

    # Intentionally fault the context assembly natively WITHOUT mocking evaluate_and_fetch_skeleton_context
    # We patch CodeStructureAtom deep inside to simulate a C-binary crash across the entire thread
    mock_atom_instance = mock_atom_class.return_value
    mock_atom_instance.run.side_effect = Exception("OS Level Binary Access Violation")

    mock_reviewer_instance = mock_reviewer_class.return_value
    mock_mock_result = MagicMock()
    mock_mock_result.verdict.value = "accepted"
    mock_mock_result.raw_response = "my valid response"
    mock_reviewer_instance.review_spec = AsyncMock(return_value=mock_mock_result)

    res = await handler.execute(step, ctx)
    assert res.status.value == "passed"

    mock_reviewer_instance.review_spec.assert_called_once()
    kwargs = mock_reviewer_instance.review_spec.call_args.kwargs
    assert "skeleton_files" in kwargs
    assert kwargs["skeleton_files"] == {}  # The fault MUST be suppressed and cleanly map empty
