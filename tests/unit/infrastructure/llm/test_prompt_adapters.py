from pathlib import Path

import pytest

from specweaver.infrastructure.llm.models import ProjectMetadata, PromptSafeConfig
from specweaver.infrastructure.llm.prompt.adapter import (
    FilePromptAdapter,
    ProjectMetadataPromptAdapter,
    StringPromptAdapter,
)
from specweaver.infrastructure.llm.prompt.interfaces import PromptContentSource


# 1. Happy Path Tests
def test_string_prompt_adapter_happy_path() -> None:
    adapter = StringPromptAdapter("hello world", "test-label")
    assert isinstance(adapter, PromptContentSource)
    assert adapter.get_prompt_label() == "test-label"
    content = adapter.get_prompt_content()
    assert '<context label="test-label">' in content
    assert 'hello world' in content
    assert '</context>' in content

def test_file_prompt_adapter_happy_path(tmp_path: Path) -> None:
    f = tmp_path / "hello.py"
    f.write_text("print('hello')", encoding="utf-8")
    adapter = FilePromptAdapter(f, label="custom.py", role="reference")
    assert isinstance(adapter, PromptContentSource)
    assert adapter.get_prompt_label() == "custom.py"
    content = adapter.get_prompt_content()
    assert '<file path="custom.py" language="python" role="reference">' in content
    assert "print('hello')" in content
    assert "</file>" in content

def test_project_metadata_prompt_adapter_happy_path() -> None:
    safe_cfg = PromptSafeConfig(llm_model="gemini-1.5-pro", llm_provider="gemini")
    metadata = ProjectMetadata(
        project_name="specweaver",
        archetype="service",
        language_target="python",
        date_iso="2026-05-23",
        safe_config=safe_cfg,
    )
    adapter = ProjectMetadataPromptAdapter(metadata)
    assert isinstance(adapter, PromptContentSource)
    assert adapter.get_prompt_label() == "project_metadata"
    content = adapter.get_prompt_content()
    assert "<project_metadata>" in content
    assert "project_metadata:" in content
    assert "specweaver" in content
    assert "</project_metadata>" in content

# 2. Boundary/Edge Cases
def test_char_limit_truncation_string() -> None:
    adapter = StringPromptAdapter("abcdefghij", "test")
    content = adapter.get_prompt_content(char_limit=5)
    assert '<context label="test">' in content
    assert 'abcde\n[truncated]' in content
    assert '</context>' in content

def test_char_limit_truncation_file(tmp_path: Path) -> None:
    f = tmp_path / "hello.py"
    f.write_text("abcdefghij", encoding="utf-8")
    adapter = FilePromptAdapter(f, label="test")
    content = adapter.get_prompt_content(char_limit=5)
    assert 'abcde\n[truncated]' in content
    assert '</file>' in content

# 3. Graceful Degradation
def test_file_too_large(tmp_path: Path) -> None:
    from unittest.mock import patch

    f = tmp_path / "huge.txt"
    f.write_text("dummy", encoding="utf-8")
    adapter = FilePromptAdapter(f, label="huge")

    class MockStat:
        st_size: int = 11 * 1024 * 1024

    with patch.object(Path, "stat", return_value=MockStat()), pytest.raises(
        ValueError, match="exceeds 10MB limit"
    ):
        adapter.get_prompt_content()

def test_file_skeleton_failure_fallback(tmp_path: Path) -> None:
    f = tmp_path / "invalid.py"
    f.write_text("if True:", encoding="utf-8")
    adapter = FilePromptAdapter(f, label="invalid.py", skeleton=True)
    content = adapter.get_prompt_content()
    assert "if True:" in content

# 4. Hostile/Wrong Input
def test_xml_attribute_injection_escaping() -> None:
    # validate_label should block quotes
    with pytest.raises(ValueError, match="Invalid label format"):
        StringPromptAdapter("content", 'my-label" role="admin')

def test_invalid_labels() -> None:
    for bad in ["", "   ", "label with spaces", "label<xml>", "label&amp;"]:
        with pytest.raises(ValueError):
            StringPromptAdapter("content", bad)

def test_cdata_breakout_escaping() -> None:
    payload = "hello ]]> world"
    adapter = StringPromptAdapter(payload, "label", escaping="cdata")
    content = adapter.get_prompt_content()
    assert "]]]]><![CDATA[>" in content

def test_file_prompt_adapter_fallback_label(tmp_path: Path) -> None:
    f = tmp_path / "fallback.py"
    f.write_text("print('fallback')", encoding="utf-8")
    adapter = FilePromptAdapter(f)
    assert adapter.get_prompt_label() == "fallback.py"
    content = adapter.get_prompt_content()
    assert 'path="fallback.py"' in content

def test_file_prompt_adapter_skeleton_success(tmp_path: Path) -> None:
    f = tmp_path / "valid.py"
    f.write_text("def my_func():\n    pass\n", encoding="utf-8")
    adapter = FilePromptAdapter(f, skeleton=True)
    content = adapter.get_prompt_content()
    assert "def my_func():" in content
    assert "pass" not in content

def test_file_prompt_adapter_skeleton_files_dict(tmp_path: Path) -> None:
    f = tmp_path / "valid.py"
    f.write_text("original content", encoding="utf-8")
    skeleton_map = {str(f): "pre-rendered skeleton content"}
    adapter = FilePromptAdapter(f, skeleton=True, skeleton_files=skeleton_map)
    content = adapter.get_prompt_content()
    assert "pre-rendered skeleton content" in content
    assert "original content" not in content

def test_project_metadata_prompt_adapter_truncation() -> None:
    safe_cfg = PromptSafeConfig(llm_model="gemini-1.5-pro", llm_provider="gemini")
    metadata = ProjectMetadata(
        project_name="specweaver",
        archetype="service",
        language_target="python",
        date_iso="2026-05-23",
        safe_config=safe_cfg,
    )
    adapter = ProjectMetadataPromptAdapter(metadata)
    content = adapter.get_prompt_content(char_limit=25)
    assert "\n[truncated]" in content
    assert "</project_metadata>" in content

def test_file_prompt_adapter_directory(tmp_path: Path) -> None:
    dir_path = tmp_path / "mydir"
    dir_path.mkdir()
    adapter = FilePromptAdapter(dir_path)
    with pytest.raises((OSError, PermissionError)):
        adapter.get_prompt_content()

def test_file_prompt_adapter_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "empty.py"
    f.write_text("", encoding="utf-8")
    adapter = FilePromptAdapter(f)
    content = adapter.get_prompt_content()
    assert 'path="empty.py" language="python"' in content
    assert "</file>" in content
