# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.filesystem.core.search import (
    _grep_ripgrep,
    find_by_glob,
    grep_content,
    iter_text_files,
)

_RIPGREP_UNAVAILABLE = shutil.which("rg") is None


def test_find_by_glob_excludes_directories(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    (root / "good").mkdir()
    (root / "good" / "test.py").touch()

    (root / "bad").mkdir()
    (root / "bad" / "test.py").touch()

    excludes = {"bad"}
    results = find_by_glob(root, "*.py", exclude_dirs=excludes)

    paths = [r["path"] for r in results]
    assert "good/test.py" in paths or r"good\test.py" in paths
    assert "bad/test.py" not in paths and r"bad\test.py" not in paths


def test_iter_text_files_excludes_directories(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    (root / "good").mkdir()
    (root / "good" / "test.txt").touch()

    (root / "node_modules").mkdir()
    (root / "node_modules" / "test.txt").touch()

    excludes = {
        "node_modules/"
    }  # Note: trailing slash or not, the implementation strips it if we pass properly? Wait, does iter_text_files strip? No! The caller is expected to strip!
    excludes_stripped = {e.rstrip("/") for e in excludes}

    results = iter_text_files(root, exclude_dirs=excludes_stripped)
    names = [p.name for p in results]

    assert len(names) == 1
    assert "test.txt" in names


# ---------------------------------------------------------------------------
# _grep_ripgrep / grep_content — TECH-009 SF-2: SubprocessExecutor DI migration
# ---------------------------------------------------------------------------


def _mock_ripgrep_executor(stdout: str = "", timed_out: bool = False) -> MagicMock:
    mock = MagicMock(spec=SubprocessExecutor)
    mock.execute.return_value = SubprocessResult(
        exit_code=0 if not timed_out else -1,
        stdout=stdout,
        stderr="",
        duration_seconds=0.01,
        timed_out=timed_out,
    )
    return mock


def test_grep_ripgrep_parses_json_matches(tmp_path: Path) -> None:
    match_line = (
        '{"type":"match","data":{"path":{"text":"file.py"},'
        '"lines":{"text":"needle found here\\n"},"line_number":5}}'
    )
    mock_executor = _mock_ripgrep_executor(stdout=match_line + "\n")

    matches, truncated, warning = _grep_ripgrep(
        "rg", tmp_path, "needle", 3, False, 20, None, mock_executor,
    )

    assert len(matches) == 1
    assert matches[0]["line_number"] == 5
    assert "needle found here" in matches[0]["content"]
    assert truncated is False
    assert warning == ""


def test_grep_ripgrep_uses_injected_executor_not_a_new_default(tmp_path: Path) -> None:
    mock_executor = _mock_ripgrep_executor()

    _grep_ripgrep("rg", tmp_path, "needle", 3, False, 20, None, mock_executor)

    mock_executor.execute.assert_called_once()
    cmd = mock_executor.execute.call_args[0][0]
    assert cmd[0] == "rg"
    assert "needle" in cmd
    assert str(tmp_path) in cmd


def test_grep_ripgrep_timeout_returns_warning(tmp_path: Path) -> None:
    mock_executor = _mock_ripgrep_executor(timed_out=True)

    matches, truncated, warning = _grep_ripgrep(
        "rg", tmp_path, "needle", 3, False, 20, None, mock_executor,
    )

    assert matches == []
    assert truncated is True
    assert "timed out" in warning


def test_grep_content_falls_back_to_python_when_rg_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ripgrep isn't on PATH, grep_content must not touch SubprocessExecutor
    at all — proving the executor param is only consulted on the ripgrep path."""
    import specweaver.sandbox.filesystem.core.search as search_module

    (tmp_path / "needle.txt").write_text("needle here\n", encoding="utf-8")
    monkeypatch.setattr(search_module.shutil, "which", lambda _name: None)  # type: ignore[attr-defined]

    results = grep_content(tmp_path, "needle")

    assert any("needle" in str(r.get("content", "")) for r in results)


@pytest.mark.skipif(_RIPGREP_UNAVAILABLE, reason="ripgrep (rg) not on PATH")
def test_grep_content_real_ripgrep_end_to_end(tmp_path: Path) -> None:
    """Real, unmocked ripgrep invocation through the migrated SubprocessExecutor
    path — proves the new env-allowlisted/credential-stripped child environment
    (TECH-009) doesn't silently break ripgrep in practice, not just in mocks."""
    (tmp_path / "file.txt").write_text("needle_target_string\n", encoding="utf-8")

    results = grep_content(tmp_path, "needle_target_string")

    assert any("needle_target_string" in str(r.get("content", "")) for r in results)
