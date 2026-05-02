# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for constitution cross-component flow.

Tests the end-to-end interaction between:
    scaffold_project() → generate_constitution() → find_constitution()
    → check_constitution() → PromptBuilder.add_constitution()

These tests verify real file I/O with no mocks — exercising the full
constitution lifecycle across multiple modules.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.workspace.project.constitution import (
    CONSTITUTION_FILENAME,
    DEFAULT_MAX_CONSTITUTION_SIZE,
    check_constitution,
    find_all_constitutions,
    find_constitution,
    generate_constitution,
)
from specweaver.workspace.project.scaffold import scaffold_project

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
import asyncio

from specweaver.interfaces.cli._db_utils import bootstrap_database
from tests.fixtures.db_utils import register_test_project


def _sync_run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import nest_asyncio

        nest_asyncio.apply(loop)
        return loop.run_until_complete(coro)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _set_constitution_max_size_sync(db, project: str, size: int) -> None:
    from specweaver.workspace.store import WorkspaceRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            await repo.set_constitution_max_size(project, size)

    _sync_run(_do())


def _get_constitution_max_size_sync(db, project: str) -> int:
    from specweaver.workspace.store import WorkspaceRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            return await repo.get_constitution_max_size(project)

    return _sync_run(_do())


class TestScaffoldConstitutionIntegration:
    """Scaffold creates constitution → find/check/PromptBuilder consume it."""

    def test_scaffold_creates_findable_constitution(
        self,
        tmp_path: Path,
    ) -> None:
        """scaffold_project creates CONSTITUTION.md that find_constitution discovers."""
        result = scaffold_project(tmp_path)

        # Scaffold returns the constitution path
        assert result.constitution_file is not None
        assert result.constitution_file.exists()

        # find_constitution discovers it
        info = find_constitution(tmp_path)
        assert info is not None
        assert info.path == result.constitution_file
        assert info.is_override is False

    def test_scaffold_constitution_passes_check(
        self,
        tmp_path: Path,
    ) -> None:
        """Generated template passes check_constitution (within size budget)."""
        scaffold_project(tmp_path)

        path = tmp_path / CONSTITUTION_FILENAME
        errors = check_constitution(path)
        assert errors == [], f"Template constitution failed check: {errors}"

    def test_scaffold_constitution_fits_prompt_builder(
        self,
        tmp_path: Path,
    ) -> None:
        """Generated constitution integrates with PromptBuilder."""
        from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

        scaffold_project(tmp_path)

        info = find_constitution(tmp_path)
        assert info is not None

        result = (
            PromptBuilder()
            .add_instructions("Review this spec.")
            .add_constitution(info.content)
            .build()
        )

        assert "<constitution>" in result
        assert "non-negotiable" in result.lower()
        assert info.content.strip() in result

    def test_scaffold_constitution_in_created_list(
        self,
        tmp_path: Path,
    ) -> None:
        """CONSTITUTION.md appears in ScaffoldResult.created."""
        result = scaffold_project(tmp_path)
        assert "CONSTITUTION.md" in result.created


class TestConstitutionWalkUpIntegration:
    """Walk-up resolution with real directory structures."""

    def test_monorepo_override_and_inheritance(self, tmp_path: Path) -> None:
        """Service with override → uses override; without → inherits root."""
        # Set up a monorepo
        scaffold_project(tmp_path)

        # Create a service with its own constitution
        billing = tmp_path / "billing-svc"
        billing.mkdir()
        (billing / CONSTITUTION_FILENAME).write_text(
            "# Billing — GDPR compliance required.\n",
            encoding="utf-8",
        )

        # billing-svc spec → finds billing constitution
        billing_spec = billing / "specs" / "payment_spec.md"
        billing_info = find_constitution(tmp_path, spec_path=billing_spec)
        assert billing_info is not None
        assert "GDPR" in billing_info.content
        assert billing_info.is_override is True

        # analytics-svc spec (no override) → inherits root
        analytics = tmp_path / "analytics-svc"
        analytics.mkdir()
        analytics_spec = analytics / "specs" / "tracking_spec.md"
        analytics_info = find_constitution(tmp_path, spec_path=analytics_spec)
        assert analytics_info is not None
        assert analytics_info.is_override is False  # root constitution

        # find_all sees both
        all_c = find_all_constitutions(tmp_path)
        assert len(all_c) == 2  # root + billing


class TestConstitutionDBIntegration:
    """Database ↔ constitution size limit integration."""

    def test_db_max_size_controls_check(self, tmp_path: Path) -> None:
        """constitution_max_size from DB controls check_constitution limit."""
        from specweaver.core.config.database import Database

        bootstrap_database(str(tmp_path / ".sw" / "specweaver.db"))
        db = Database(tmp_path / ".sw" / "specweaver.db")
        register_test_project(db, "myapp", str(tmp_path))

        # Default is 5120
        max_size = _get_constitution_max_size_sync(db, "myapp")
        assert max_size == DEFAULT_MAX_CONSTITUTION_SIZE

        # Write a constitution exactly at default limit
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("x" * max_size, encoding="utf-8")
        assert check_constitution(path, max_size=max_size) == []

        # Reduce limit in DB → same file now fails check
        _set_constitution_max_size_sync(db, "myapp", 100)
        new_max = _get_constitution_max_size_sync(db, "myapp")
        errors = check_constitution(path, max_size=new_max)
        assert len(errors) >= 1


class TestConstitutionLogging:
    """Verify that constitution operations produce expected log output."""

    def test_find_logs_info_on_success(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """find_constitution logs INFO when a constitution is found."""
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            "# Rules",
            encoding="utf-8",
        )
        with caplog.at_level(logging.INFO, logger="specweaver.workspace.project.constitution"):
            find_constitution(tmp_path)

        assert any("loaded" in r.message.lower() for r in caplog.records)

    def test_find_logs_debug_on_miss(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """find_constitution logs DEBUG when no constitution found."""
        with caplog.at_level(logging.DEBUG, logger="specweaver.workspace.project.constitution"):
            find_constitution(tmp_path)

        assert any("no constitution" in r.message.lower() for r in caplog.records)

    def test_generate_logs_info_on_create(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """generate_constitution logs INFO when creating a new file."""
        with caplog.at_level(logging.INFO, logger="specweaver.workspace.project.constitution"):
            generate_constitution(tmp_path, "test-app")

        assert any("generated" in r.message.lower() for r in caplog.records)

    def test_oversize_logs_warning(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """find_constitution logs WARNING for oversized constitutions."""
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            "x" * (DEFAULT_MAX_CONSTITUTION_SIZE + 100),
            encoding="utf-8",
        )
        with caplog.at_level(logging.WARNING, logger="specweaver.workspace.project.constitution"):
            find_constitution(tmp_path)

        assert any("exceeds" in r.message.lower() for r in caplog.records)
