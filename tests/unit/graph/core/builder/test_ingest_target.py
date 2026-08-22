# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Collecting and ingesting a target, once per file.

Proves: TECH-068 NFR-1, NFR-2

Both budgets rest on the same quantity — the per-file cost — so both rest on the same mechanism:
each collected file is read exactly once. `ingest_target` used to call `ingest_file`, which re-reads
the file, and a second read doubles the number the 60 s and 5 s budgets are measured against.

A wall-clock assertion is the wrong instrument for those budgets: it measures the machine running
CI as much as the code, and a flaky performance test gets deleted rather than investigated. The
figures are re-measured at closure and recorded in the design; what a test can hold is the property
that keeps them true.
"""

from __future__ import annotations

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
    """[Happy Path] ingest_target ingests a single file exactly once.

    Asserts the outcome rather than the delegation. `ingest_target` used to call `ingest_file`,
    which re-reads the file; it now reuses what the prepass already read, because parsing twice
    doubles the per-file cost `TECH-068` NFR-1 is measured against. The claim was never that one
    method calls another — it is that each collected file is ingested once.
    """
    f = tmp_path / "foo.py"
    f.write_text("")

    mock_ingest = MagicMock()
    monkeypatch.setattr(builder, "ingest_ast", mock_ingest)

    count = builder.ingest_target(f)

    assert count == 1
    assert [call.args[0] for call in mock_ingest.call_args_list] == [str(f)]


def test_ingest_target_directory(builder, monkeypatch, tmp_path):
    """[Happy Path] ingest_target ingests every file in the directory, each exactly once."""
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")

    mock_ingest = MagicMock()
    monkeypatch.setattr(builder, "ingest_ast", mock_ingest)

    count = builder.ingest_target(tmp_path)

    assert count == 2
    assert mock_ingest.call_count == 2
    assert sorted(call.args[0] for call in mock_ingest.call_args_list) == sorted(
        [str(tmp_path / "a.py"), str(tmp_path / "b.py")]
    )


def test_ingest_target_empty_directory(builder, monkeypatch, tmp_path):
    """[Boundary] Empty directory ingests nothing."""
    mock_ingest = MagicMock()
    monkeypatch.setattr(builder, "ingest_ast", mock_ingest)

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
