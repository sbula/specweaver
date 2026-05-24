# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for interfaces/cli/_core.py — run_repo_op and _require_active_project."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

# ---------------------------------------------------------------------------
# run_repo_op
# ---------------------------------------------------------------------------


class TestRunRepoOp:
    """Test run_repo_op typed repository helper."""

    def test_happy_path_returns_result(self) -> None:
        """Typed lambda result is returned correctly."""
        from specweaver.interfaces.cli._core import run_repo_op

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.async_session_scope.return_value = mock_session

        with patch("specweaver.interfaces.cli._core.get_db", return_value=mock_db):
            result = run_repo_op(lambda r: _async_return("test-project"))

        assert result == "test-project"

    def test_returns_none_when_repo_returns_none(self) -> None:
        """None result from repo is returned unchanged."""
        from specweaver.interfaces.cli._core import run_repo_op

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.async_session_scope.return_value = mock_session

        with patch("specweaver.interfaces.cli._core.get_db", return_value=mock_db):
            result = run_repo_op(lambda r: _async_return(None))

        assert result is None

    def test_returns_list(self) -> None:
        """List results pass through correctly."""
        from specweaver.interfaces.cli._core import run_repo_op

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.async_session_scope.return_value = mock_session

        with patch("specweaver.interfaces.cli._core.get_db", return_value=mock_db):
            result = run_repo_op(lambda r: _async_return(["a", "b", "c"]))

        assert result == ["a", "b", "c"]

    def test_exception_propagates(self) -> None:
        """Exceptions from the lambda propagate to the caller."""
        from specweaver.interfaces.cli._core import run_repo_op

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.async_session_scope.return_value = mock_session

        async def _raise(_r):
            raise ValueError("repo error")

        with (
            patch("specweaver.interfaces.cli._core.get_db", return_value=mock_db),
            pytest.raises(ValueError, match="repo error"),
        ):
            run_repo_op(_raise)

    def test_session_scope_is_closed_after_call(self) -> None:
        """async_session_scope __aexit__ is called (session is closed)."""
        from specweaver.interfaces.cli._core import run_repo_op

        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.async_session_scope.return_value = mock_session

        with patch("specweaver.interfaces.cli._core.get_db", return_value=mock_db):
            run_repo_op(lambda r: _async_return("x"))

        mock_session.__aexit__.assert_called_once()


# ---------------------------------------------------------------------------
# _require_active_project
# ---------------------------------------------------------------------------


class TestRequireActiveProject:
    """Test _require_active_project using run_repo_op."""

    def test_returns_project_name_when_active(self) -> None:
        """Returns project name string when active project exists."""
        from specweaver.interfaces.cli import _core

        with (
            patch.object(_core, "run_repo_op", return_value="my-project"),
            patch.object(_core, "get_db", return_value=MagicMock()),
        ):
            result = _core._require_active_project()

        assert result == "my-project"

    def test_exits_when_no_active_project(self) -> None:
        """Raises typer.Exit(code=1) when no active project."""
        from specweaver.interfaces.cli import _core

        with (
            patch.object(_core, "run_repo_op", return_value=None),
            patch.object(_core, "get_db", return_value=MagicMock()),
            pytest.raises(typer.Exit) as exc_info,
        ):
            _core._require_active_project()

        assert exc_info.value.exit_code == 1

    def test_exits_when_empty_string(self) -> None:
        """Empty string is falsy → also exits."""
        from specweaver.interfaces.cli import _core

        with (
            patch.object(_core, "run_repo_op", return_value=""),
            patch.object(_core, "get_db", return_value=MagicMock()),
            pytest.raises(typer.Exit) as exc_info,
        ):
            _core._require_active_project()

        assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# run_repo_op — exported in __all__
# ---------------------------------------------------------------------------


class TestRunRepoOpExported:
    """Verify run_repo_op is in __all__."""

    def test_in_all(self) -> None:
        from specweaver.interfaces.cli import _core

        assert "run_repo_op" in _core.__all__


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _async_return(value):
    return value
