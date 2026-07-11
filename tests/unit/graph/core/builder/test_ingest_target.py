# mypy: ignore-errors
from unittest.mock import MagicMock

import pytest

from specweaver.graph.core.builder.orchestrator import GraphBuilder


@pytest.fixture
def mock_engine():
    return MagicMock()


@pytest.fixture
def builder(mock_engine):
    # Mock parser to avoid actual parsing in tests
    return GraphBuilder(mock_engine, parser=MagicMock())


def test_collect_files_single_file(builder, tmp_path):
    """[Happy Path] collect_files returns the file path if target is a file."""
    f = tmp_path / "foo.py"
    f.write_text("print('hello')")

    files = builder.collect_files(f)
    assert files == {str(f)}


def test_collect_files_directory(builder, tmp_path):
    """[Happy Path] collect_files recursively finds .py files in a directory."""
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.txt").write_text("")  # Should be ignored
    d = tmp_path / "sub"
    d.mkdir()
    (d / "c.py").write_text("")

    files = builder.collect_files(tmp_path)

    # Normalizes paths using SemanticHasher.normalize_path or just uses strings?
    # The builder should probably use string paths.
    assert len(files) == 2
    assert any("a.py" in f for f in files)
    assert any("c.py" in f for f in files)
    assert not any("b.txt" in f for f in files)


def test_ingest_target_single_file(builder, monkeypatch, tmp_path):
    """[Happy Path] ingest_target calls ingest_file once for a single file."""
    f = tmp_path / "foo.py"
    f.write_text("")

    mock_ingest = MagicMock()
    monkeypatch.setattr(builder, "ingest_file", mock_ingest)

    count = builder.ingest_target(f)

    assert count == 1
    mock_ingest.assert_called_once_with(str(f))


def test_ingest_target_directory(builder, monkeypatch, tmp_path):
    """[Happy Path] ingest_target calls ingest_file for each file in directory."""
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")

    mock_ingest = MagicMock()
    monkeypatch.setattr(builder, "ingest_file", mock_ingest)

    count = builder.ingest_target(tmp_path)

    assert count == 2
    assert mock_ingest.call_count == 2


def test_ingest_target_empty_directory(builder, monkeypatch, tmp_path):
    """[Boundary] Empty directory calls ingest_file 0 times."""
    mock_ingest = MagicMock()
    monkeypatch.setattr(builder, "ingest_file", mock_ingest)

    count = builder.ingest_target(tmp_path)

    assert count == 0
    mock_ingest.assert_not_called()


def test_ingest_target_nonexistent(builder, monkeypatch, tmp_path):
    """[Graceful Degradation] Non-existent path is treated as a single file and passed to ingest_file."""
    f = tmp_path / "does_not_exist.py"

    mock_ingest = MagicMock()
    monkeypatch.setattr(builder, "ingest_file", mock_ingest)

    count = builder.ingest_target(f)

    assert count == 1
    mock_ingest.assert_called_once_with(str(f))
