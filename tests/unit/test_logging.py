# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for specweaver.logging module."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest
from rich.logging import RichHandler

from specweaver.logging import (
    BACKUP_COUNT,
    LOG_LEVELS,
    MAX_BYTES,
    get_log_path,
    setup_logging,
    teardown_logging,
)


@pytest.fixture(autouse=True)
def _clean_logging():
    """Ensure logging state is clean before and after each test."""
    teardown_logging()
    yield
    teardown_logging()


# ---------------------------------------------------------------------------
# JSONFormatter
# ---------------------------------------------------------------------------


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_valid_json(self):
        from specweaver.logging import JSONFormatter

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)

        parsed = json.loads(output)
        assert "timestamp" in parsed
        assert parsed["levelname"] == "INFO"
        assert parsed["name"] == "test.logger"
        assert parsed["message"] == "Hello world"
        assert "exc_info" not in parsed

    def test_format_includes_exc_info(self):
        import sys

        from specweaver.logging import JSONFormatter

        formatter = JSONFormatter()

        try:
            _ = 1 / 0
        except ZeroDivisionError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=20,
            msg="Failed",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exc_info" in parsed
        assert "ZeroDivisionError" in parsed["exc_info"]


# ---------------------------------------------------------------------------
# get_log_path
# ---------------------------------------------------------------------------


class TestGetLogPath:
    """Tests for get_log_path()."""

    def test_returns_path_under_specweaver_logs(self):
        path = get_log_path("myproject")
        assert path == Path.home() / ".specweaver" / "logs" / "myproject" / "specweaver.log"

    def test_returns_path_type(self):
        path = get_log_path("test")
        assert isinstance(path, Path)

    def test_different_projects_get_different_paths(self):
        p1 = get_log_path("alpha")
        p2 = get_log_path("beta")
        assert p1 != p2
        assert "alpha" in str(p1)
        assert "beta" in str(p2)


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------


class TestSetupLogging:
    """Tests for setup_logging()."""

    def test_creates_file_and_console_handlers(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("testprj")
        root = logging.getLogger("specweaver")
        assert len(root.handlers) == 2
        handler_types = {type(h) for h in root.handlers}
        assert RotatingFileHandler in handler_types
        assert RichHandler in handler_types

    def test_file_handler_uses_correct_path(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("myprj")
        root = logging.getLogger("specweaver")
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1
        assert "myprj" in file_handlers[0].baseFilename
        assert "specweaver.log" in file_handlers[0].baseFilename

    def test_file_handler_uses_rotation_settings(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj")
        root = logging.getLogger("specweaver")
        file_handler = next(h for h in root.handlers if isinstance(h, RotatingFileHandler))
        assert file_handler.maxBytes == MAX_BYTES
        assert file_handler.backupCount == BACKUP_COUNT

    def test_console_handler_at_warning_level(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj")
        root = logging.getLogger("specweaver")
        console_handler = next(h for h in root.handlers if isinstance(h, RichHandler))
        assert console_handler.level == logging.WARNING

    def test_file_handler_at_configured_level(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj", level="INFO")
        root = logging.getLogger("specweaver")
        file_handler = next(h for h in root.handlers if isinstance(h, RotatingFileHandler))
        assert file_handler.level == logging.INFO

    def test_default_level_is_debug(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj")
        root = logging.getLogger("specweaver")
        file_handler = next(h for h in root.handlers if isinstance(h, RotatingFileHandler))
        assert file_handler.level == logging.DEBUG

    def test_fallback_project_name_when_none(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging(None)
        root = logging.getLogger("specweaver")
        file_handler = next(h for h in root.handlers if isinstance(h, RotatingFileHandler))
        assert "_global" in file_handler.baseFilename

    def test_idempotent_same_project(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj")
        setup_logging("proj")
        root = logging.getLogger("specweaver")
        # Should still have exactly 2 handlers (not 4)
        assert len(root.handlers) == 2

    def test_project_change_replaces_handlers(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj-a")
        setup_logging("proj-b")
        root = logging.getLogger("specweaver")
        assert len(root.handlers) == 2
        file_handler = next(h for h in root.handlers if isinstance(h, RotatingFileHandler))
        assert "proj-b" in file_handler.baseFilename

    def test_invalid_level_falls_back_to_debug(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj", level="INVALID")
        root = logging.getLogger("specweaver")
        file_handler = next(h for h in root.handlers if isinstance(h, RotatingFileHandler))
        assert file_handler.level == logging.DEBUG

    def test_log_formatters_are_configured_correctly(self, tmp_path, monkeypatch):
        from specweaver.logging import JSONFormatter

        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj")
        root = logging.getLogger("specweaver")

        file_handler = next(h for h in root.handlers if isinstance(h, RotatingFileHandler))
        assert isinstance(file_handler.formatter, JSONFormatter)

        console_handler = next(h for h in root.handlers if isinstance(h, RichHandler))
        assert console_handler.formatter is not None
        assert console_handler.formatter._fmt == "%(message)s"
        assert console_handler.formatter.datefmt == "[%X]"

    def test_creates_log_directory(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("newprj")
        log_dir = tmp_path / "logs" / "newprj"
        assert log_dir.exists()

    def test_logs_are_written_to_file(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("writetest")
        logger = logging.getLogger("specweaver.test")
        logger.info("Test message 42")

        log_file = tmp_path / "logs" / "writetest" / "specweaver.log"
        content = log_file.read_text(encoding="utf-8")
        assert "Test message 42" in content

    def test_case_insensitive_level(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj", level="info")
        root = logging.getLogger("specweaver")
        file_handler = next(h for h in root.handlers if isinstance(h, RotatingFileHandler))
        assert file_handler.level == logging.INFO


# ---------------------------------------------------------------------------
# teardown_logging
# ---------------------------------------------------------------------------


class TestTeardownLogging:
    """Tests for teardown_logging()."""

    def test_removes_all_handlers(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj")
        assert len(logging.getLogger("specweaver").handlers) == 2
        teardown_logging()
        assert len(logging.getLogger("specweaver").handlers) == 0

    def test_removes_project_tag(self, tmp_path, monkeypatch):
        _logs = tmp_path / "logs"
        monkeypatch.setattr(
            "specweaver.config.paths.logs_dir",
            lambda: _logs,
        )
        setup_logging("proj")
        teardown_logging()
        assert not hasattr(logging.getLogger("specweaver"), "_sw_project")

    def test_idempotent_teardown(self):
        teardown_logging()
        teardown_logging()  # Should not raise


# ---------------------------------------------------------------------------
# LOG_LEVELS constant
# ---------------------------------------------------------------------------


class TestLogLevels:
    """Tests for LOG_LEVELS dictionary."""

    def test_all_standard_levels_present(self):
        assert set(LOG_LEVELS.keys()) == {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

    def test_values_are_correct(self):
        assert LOG_LEVELS["DEBUG"] == logging.DEBUG
        assert LOG_LEVELS["INFO"] == logging.INFO
        assert LOG_LEVELS["WARNING"] == logging.WARNING
        assert LOG_LEVELS["ERROR"] == logging.ERROR
        assert LOG_LEVELS["CRITICAL"] == logging.CRITICAL
