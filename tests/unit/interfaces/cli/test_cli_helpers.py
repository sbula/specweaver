# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests — CLI _helpers module.

Tests: _print_summary, _select_topology_contexts,
       _load_constitution_content, _load_standards_content.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import typer

from specweaver.assurance.validation.models import RuleResult, Status


@pytest.fixture(autouse=True)
def _mock_db_fixture(tmp_path, monkeypatch):
    from specweaver.core.config.database import Database

    with patch("specweaver.core.config.database.Database._ensure_schema", create=True):
        from specweaver.core.config.db_bootstrap import bootstrap_database

        bootstrap_database(str(tmp_path / ".sw-test" / "specweaver.db"))
        db = Database(tmp_path / ".sw-test" / "specweaver.db")
        monkeypatch.setattr("specweaver.core.config.db_bootstrap.get_db", lambda: db)
        return db


# ---------------------------------------------------------------------------
# _print_summary
# ---------------------------------------------------------------------------


class TestPrintSummary:
    """Test _print_summary exit-code logic."""

    def _make_result(self, status: Status) -> RuleResult:
        return RuleResult(
            rule_id="S01",
            rule_name="Test Rule",
            status=status,
            message="msg",
        )

    def test_all_pass_no_exit(self) -> None:
        """All PASS results → no exit raised."""
        from specweaver.assurance.validation.interfaces.cli import _print_summary

        results = [self._make_result(Status.PASS)]
        _print_summary(results)  # should not raise

    def test_fail_raises_exit_1(self) -> None:
        """Any FAIL result → typer.Exit(code=1)."""
        from specweaver.assurance.validation.interfaces.cli import _print_summary

        results = [
            self._make_result(Status.PASS),
            self._make_result(Status.FAIL),
        ]
        with pytest.raises(typer.Exit) as exc_info:
            _print_summary(results)
        assert exc_info.value.exit_code == 1

    def test_warn_no_exit_default(self) -> None:
        """WARN without strict → no exit raised."""
        from specweaver.assurance.validation.interfaces.cli import _print_summary

        results = [self._make_result(Status.WARN)]
        _print_summary(results)  # should not raise

    def test_warn_strict_raises_exit_1(self) -> None:
        """WARN with strict=True → typer.Exit(code=1)."""
        from specweaver.assurance.validation.interfaces.cli import _print_summary

        results = [self._make_result(Status.WARN)]
        with pytest.raises(typer.Exit) as exc_info:
            _print_summary(results, strict=True)
        assert exc_info.value.exit_code == 1

    def test_mixed_fail_and_warn(self) -> None:
        """FAIL takes priority over WARN → exit(1)."""
        from specweaver.assurance.validation.interfaces.cli import _print_summary

        results = [
            self._make_result(Status.WARN),
            self._make_result(Status.FAIL),
        ]
        with pytest.raises(typer.Exit) as exc_info:
            _print_summary(results)
        assert exc_info.value.exit_code == 1

    def test_empty_results_no_exit(self) -> None:
        """Empty results list → no exit raised."""
        from specweaver.assurance.validation.interfaces.cli import _print_summary

        _print_summary([])  # should not raise
