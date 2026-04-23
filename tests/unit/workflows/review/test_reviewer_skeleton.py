from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.workflows.review.reviewer import Reviewer, ReviewVerdict


@patch("specweaver.infrastructure.llm.prompt_builder.PromptBuilder")
@pytest.mark.asyncio
async def test_reviewer_accepts_skeleton_files(mock_pb_class, tmp_path: Path) -> None:
    """Story 8: Reviewer accepts skeleton_files implicitly and propagates it."""
    spec_path = tmp_path / "foo_spec.md"
    spec_path.write_text("spec")

    code_path = tmp_path / "foo.py"
    code_path.write_text("code")

    mock_llm = AsyncMock()
    mock_response = AsyncMock()
    mock_response.text = "VERDICT: ACCEPTED\n- looks good [confidence: 100]"
    mock_llm.generate.return_value = mock_response

    # We patch PromptBuilder to monitor its kwargs
    pb_instance = mock_pb_class.return_value
    pb_instance.add_instructions.return_value = pb_instance
    pb_instance.add_project_metadata.return_value = pb_instance
    pb_instance.add_file.return_value = pb_instance
    pb_instance.build.return_value = "fake prompt"

    s_files = {"c:/dummy/file.py": "def skel(): pass"}

    rev = Reviewer(mock_llm)
    res = await rev.review_code(code_path, spec_path, skeleton_files=s_files)

    mock_pb_class.assert_called_once_with(skeleton_files=s_files)
    assert res.verdict == ReviewVerdict.ACCEPTED
