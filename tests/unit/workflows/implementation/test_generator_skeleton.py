from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.workflows.implementation.generator import Generator


@patch("specweaver.infrastructure.llm.prompt_builder.PromptBuilder")
@pytest.mark.asyncio
async def test_generator_accepts_skeleton_files(mock_pb_class, tmp_path: Path) -> None:
    """Story 7: Generator accepts skeleton_files implicitly and propagates it."""
    spec_path = tmp_path / "foo_spec.md"
    out_path = tmp_path / "foo.py"
    spec_path.write_text("spec")

    mock_llm = AsyncMock()
    mock_response = AsyncMock()
    mock_response.text = "```python\ndef test(): pass\n```"
    mock_llm.generate.return_value = mock_response

    # We patch PromptBuilder to monitor its kwargs
    pb_instance = mock_pb_class.return_value
    pb_instance.add_instructions.return_value = pb_instance
    pb_instance.add_project_metadata.return_value = pb_instance
    pb_instance.add_file.return_value = pb_instance
    pb_instance.build.return_value = "fake prompt"

    s_files = {"c:/dummy/file.py": "def skel(): pass"}

    gen = Generator(mock_llm)
    await gen.generate_code(spec_path, out_path, skeleton_files=s_files)

    mock_pb_class.assert_called_once_with(skeleton_files=s_files)
