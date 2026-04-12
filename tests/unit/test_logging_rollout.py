# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for logging rollout — verifies key modules emit structured log records.

This test file grows incrementally across the 4 commit boundaries of
the SF-3 Logging Rollout (Feature 3.13a).  Each TestBatch* class covers
one architectural layer.  Tests use pytest's ``caplog`` fixture
to verify that instrumented modules emit the expected log records.
"""

from __future__ import annotations

import logging

# ---------------------------------------------------------------------------
# Batch 1: Core Infrastructure (config/, context/, project/)
# ---------------------------------------------------------------------------


class TestBatch1LoggingRollout:
    """Verify Batch 1 modules emit log records."""

    def test_settings_module_has_logger(self):
        """config/settings.py should declare a module-level logger."""
        from specweaver.core.config import settings

        assert hasattr(settings, "logger"), "settings module must have a logger"
        assert isinstance(settings.logger, logging.Logger)
        assert settings.logger.name == "specweaver.core.config.settings"

    def test_load_settings_emits_debug_log(self, caplog, tmp_path, monkeypatch):
        """load_settings() should emit a DEBUG entry log."""
        from unittest.mock import MagicMock

        from specweaver.core.config.settings import load_settings

        with caplog.at_level(logging.DEBUG, logger="specweaver.core.config.settings"):
            try:
                mock_db = MagicMock()
                mock_db.get_project.return_value = None
                load_settings(mock_db, "nonexistent")
            except (ValueError, TypeError, AttributeError):
                pass  # expected — we only care about the log

        assert any(
            "load_settings" in r.message and r.levelno == logging.DEBUG for r in caplog.records
        ), "load_settings() should emit a DEBUG-level entry log"

    def test_paths_module_has_logger(self):
        """config/paths.py should declare a module-level logger."""
        from specweaver.core.config import paths

        assert hasattr(paths, "logger"), "paths module must have a logger"
        assert isinstance(paths.logger, logging.Logger)
        assert paths.logger.name == "specweaver.core.config.paths"


class TestBatch4LoggingRollout:
    """Verify Batch 4 modules (Entry Points) emit log records."""

    def test_cli_modules_have_loggers(self):
        """CLI modules must have loggers."""
        from specweaver.interfaces.cli import (
            config,
            config_routing,
            constitution,
            cost_commands,
            implement,
            pipelines,
            projects,
            review,
            serve,
            standards,
            usage_commands,
            validation,
        )

        for mod in (
            config,
            config_routing,
            constitution,
            cost_commands,
            implement,
            pipelines,
            projects,
            review,
            serve,
            standards,
            usage_commands,
            validation,
        ):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__

    def test_api_modules_have_loggers(self):
        """API modules must have loggers."""
        from specweaver.interfaces.api.v1 import (
            constitution,
            health,
            implement,
            paths,
            pipelines,
            projects,
            review,
            standards,
            validation,
            ws,
        )

        for mod in (
            constitution,
            health,
            implement,
            paths,
            pipelines,
            projects,
            review,
            standards,
            validation,
            ws,
        ):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__
