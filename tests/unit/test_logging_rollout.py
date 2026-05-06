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
        """Loading settings emits a DEBUG log entry with the project path."""
        from unittest.mock import MagicMock

        from specweaver.core.config.settings_loader import load_settings

        with caplog.at_level(logging.DEBUG, logger="specweaver.core.config.settings_loader"):
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

    def test_profiles_module_has_logger(self):
        """config/profiles.py should declare a module-level logger."""
        from specweaver.core.config import profiles

        assert hasattr(profiles, "logger"), "profiles module must have a logger"
        assert isinstance(profiles.logger, logging.Logger)
        assert profiles.logger.name == "specweaver.core.config.profiles"

    def test_database_module_has_logger(self):
        """config/database.py should declare a module-level logger."""
        from specweaver.core.config import database

        assert hasattr(database, "logger"), "database module must have a logger"
        assert isinstance(database.logger, logging.Logger)
        assert database.logger.name == "specweaver.core.config.database"

    def test_context_modules_have_loggers(self):
        """workspace/context modules should declare loggers."""
        from specweaver.workspace.context import (
            analyzer_protocols,
            hitl_provider,
            inferrer,
            provider,
        )

        for mod in (analyzer_protocols, hitl_provider, inferrer, provider):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__

    def test_project_modules_have_loggers(self):
        """workspace/project modules should declare loggers."""
        from specweaver.workspace.project import (
            _helpers,
            constitution,
            discovery,
            scaffold,
        )

        for mod in (_helpers, constitution, discovery, scaffold):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__

    def test_ast_modules_have_loggers(self):
        """workspace/ast modules should declare loggers."""
        from specweaver.workspace.ast.adapters import graph_adapter
        from specweaver.workspace.ast.parsers import factory, interfaces
        from specweaver.workspace.ast.parsers.c import codestructure as c_cs
        from specweaver.workspace.ast.parsers.cpp import codestructure as cpp_cs
        from specweaver.workspace.ast.parsers.java import parsers as java_p
        from specweaver.workspace.ast.parsers.kotlin import parsers as kotlin_p
        from specweaver.workspace.ast.parsers.rust import parsers as rust_p
        from specweaver.workspace.ast.parsers.typescript import parsers as ts_p

        for mod in (
            graph_adapter,
            factory,
            interfaces,
            c_cs,
            cpp_cs,
            java_p,
            kotlin_p,
            rust_p,
            ts_p,
        ):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__


# ---------------------------------------------------------------------------
# Batch 2: Domain Logic (assurance/, graph/, workflows/)
# ---------------------------------------------------------------------------


class TestBatch2LoggingRollout:
    """Verify Batch 2 modules emit log records."""

    def test_validation_modules_have_loggers(self):
        """assurance/validation modules should declare loggers."""
        from specweaver.assurance.validation import (
            executor,
            inheritance,
            loader,
            pipeline,
            pipeline_loader,
            registry,
            runner,
            spec_kind,
        )

        for mod in (
            executor,
            inheritance,
            loader,
            pipeline,
            pipeline_loader,
            registry,
            runner,
            spec_kind,
        ):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__

    def test_standards_modules_have_loggers(self):
        """assurance/standards modules should declare loggers."""
        from specweaver.assurance.standards import (
            analyzer,
            discovery,
            enricher,
            loader,
            recency,
            reviewer,
            scanner,
            scope_detector,
            tree_sitter_base,
        )

        for mod in (
            analyzer,
            discovery,
            enricher,
            loader,
            recency,
            reviewer,
            scanner,
            scope_detector,
            tree_sitter_base,
        ):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__

    def test_graph_and_planning_modules_have_loggers(self):
        """graph/ and workflows/planning modules should declare loggers."""
        from specweaver.assurance.graph import selectors, topology
        from specweaver.workflows.planning import planner, renderer, stitch, ui_extractor

        for mod in (selectors, topology, planner, renderer, stitch, ui_extractor):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__

    def test_workflow_modules_have_loggers(self):
        """workflows/ drafting, review, implementation should declare loggers."""
        from specweaver.workflows.drafting import drafter, feature_drafter
        from specweaver.workflows.implementation import generator
        from specweaver.workflows.review import reviewer

        for mod in (drafter, feature_drafter, generator, reviewer):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__


class TestBatch4LoggingRollout:
    """Verify Batch 4 modules (Entry Points) emit log records."""

    def test_cli_modules_have_loggers(self):
        """CLI modules must have loggers."""
        from specweaver.assurance.standards.interfaces import cli as standards
        from specweaver.core.config.interfaces import cli as config
        from specweaver.core.flow.interfaces import cli as flow_cli
        from specweaver.infrastructure.llm.interfaces import cli as llm_cli
        from specweaver.interfaces.cli import main
        from specweaver.interfaces.cli.routers import serve_router as serve
        from specweaver.workspace.project.interfaces import cli as workspace

        # Ensure that every Typer command module defines a module-level logger
        assert hasattr(main, "logger")
        assert hasattr(config, "logger")
        assert hasattr(workspace, "logger")
        assert hasattr(llm_cli, "logger")
        assert hasattr(flow_cli, "logger")
        assert hasattr(serve, "logger")
        assert hasattr(standards, "logger"), "standards must have a logger"

        for mod in (config, workspace, llm_cli, flow_cli, serve, standards):
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


class TestBatch3LoggingRollout:
    """Verifies that Batch 3 (LLM & Flow Engine) modules have standard loggers."""

    def test_infrastructure_llm_loggers(self) -> None:
        from specweaver.infrastructure.llm import (
            _prompt_render,
            prompt_builder,
            telemetry,
        )
        from specweaver.infrastructure.llm.mention_scanner import scanner

        for mod in (prompt_builder, telemetry, _prompt_render, scanner):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__

    def test_infrastructure_llm_adapters_loggers(self) -> None:
        import logging

        from specweaver.infrastructure.llm.adapters import (
            _rate_limit,
            anthropic,
            base,
            gemini,
            mistral,
            openai,
            qwen,
            registry,
        )

        for mod in (
            anthropic,
            base,
            gemini,
            mistral,
            openai,
            qwen,
            registry,
            _rate_limit,
        ):
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__

    def test_core_flow_loggers(self) -> None:
        import logging

        from specweaver.core.flow.engine import (
            display,
            gates,
            parser,
            reservation,
            routers,
            runner,
            runner_utils,
            store,
        )
        from specweaver.core.flow.handlers import (
            arbiter,
            base,
            context_assembler,
            contract_renderers,
            decompose,
            draft,
            drift,
            dual_pipeline,
            generation,
            lint_fix,
            mcp_assembler,
            registry,
            review,
            scenario,
            standards,
            validation,
        )
        from specweaver.core.flow.interfaces import cli

        modules = [
            display,
            gates,
            parser,
            reservation,
            routers,
            runner,
            runner_utils,
            store,
            arbiter,
            base,
            context_assembler,
            contract_renderers,
            decompose,
            draft,
            drift,
            dual_pipeline,
            generation,
            lint_fix,
            mcp_assembler,
            registry,
            review,
            scenario,
            standards,
            validation,
            cli,
        ]

        for mod in modules:
            assert hasattr(mod, "logger"), f"{mod.__name__} must have a logger"
            assert isinstance(mod.logger, logging.Logger)
            assert mod.logger.name == mod.__name__
