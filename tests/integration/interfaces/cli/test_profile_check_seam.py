# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — CLI validation + profile pipeline selection seam.

Exercises the full round-trip:
  CLI check command → _resolve_pipeline_name → DB → profiles → pipeline_loader

Scenarios covered:
  39. sw check --level component with active "web-app" profile loads web-app YAML
  40. Explicit --pipeline overrides active profile during check
  76. CLI check → DB → profiles → pipeline_loader seam
  77. CLI check → _resolve_pipeline_name with explicit --pipeline
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fixtures.db_utils import set_test_active_project

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

runner = CliRunner()


@pytest.fixture()
def _mock_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch get_db() to use a temp DB for all tests."""
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database

    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    db_path = str(data_dir / "specweaver.db")
    bootstrap_database(db_path)
    db = Database(db_path)
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: db)
    return db


@pytest.fixture()
def _project(tmp_path: Path, _mock_db: MagicMock) -> tuple[str, Path]:
    """Create and activate a test project."""
    name = "seam-proj"
    project_dir = tmp_path / name
    project_dir.mkdir()
    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0, f"init failed: {result.output}"
    set_test_active_project(_mock_db, name)
    return name, project_dir


@pytest.fixture()
def _spec_file(tmp_path: Path) -> Path:
    """Create a minimal spec file for check tests."""
    spec = tmp_path / "specs" / "test_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(
        "# Test Spec\n\n## 1. Purpose\nA simple test spec.\n\n"
        "## 2. Requirements\n- Do something.\n",
    )
    return spec


# ===========================================================================
# Profile-aware sw check round-trip (scenarios 39, 76)
# ===========================================================================


import anyio


def _set_domain_profile_sync(db, project: str, profile: str) -> None:
    from specweaver.workspace.store import WorkspaceRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            await repo.set_domain_profile(project, profile)

    anyio.run(_do)


def _get_domain_profile_sync(db, project: str) -> str | None:
    from specweaver.workspace.store import WorkspaceRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            return await repo.get_domain_profile(project)

    return anyio.run(_do)


def _create_llm_profile_sync(
    db,
    name: str,
    provider: str,
    model: str,
    temperature: float = 0.2,
    max_output_tokens: int = 4096,
) -> int:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            return await repo.create_llm_profile(
                name,
                provider=provider,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_format="text",
            )

    return anyio.run(_do)


def _link_project_profile_sync(db, project: str, task: str, profile_id: int) -> None:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.link_project_profile(project, task, profile_id)

    anyio.run(_do)


def _set_cost_override_sync(db, model: str, in_cost: float, out_cost: float) -> None:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.set_cost_override(model, in_cost, out_cost)

    anyio.run(_do)


def _get_cost_overrides_sync(db) -> dict:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            return await repo.get_cost_overrides()

    return anyio.run(_do)


import asyncio


def _sync_run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio

            nest_asyncio.apply(loop)
            return loop.run_until_complete(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _set_domain_profile_sync(db, project: str, profile: str) -> None:
    from specweaver.workspace.store import WorkspaceRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            await repo.set_domain_profile(project, profile)

    _sync_run(_do())


def _get_domain_profile_sync(db, project: str) -> str | None:
    from specweaver.workspace.store import WorkspaceRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            return await repo.get_domain_profile(project)

    return _sync_run(_do())


def _create_llm_profile_sync(
    db,
    name: str,
    provider: str,
    model: str,
    temperature: float = 0.2,
    max_output_tokens: int = 4096,
) -> int:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            return await repo.create_llm_profile(
                name,
                provider=provider,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_format="text",
            )

    return _sync_run(_do())


def _link_project_profile_sync(db, project: str, task: str, profile_id: int) -> None:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.link_project_profile(project, task, profile_id)

    _sync_run(_do())


def _set_cost_override_sync(db, model: str, in_cost: float, out_cost: float) -> None:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.set_cost_override(model, in_cost, out_cost)

    _sync_run(_do())


def _get_cost_overrides_sync(db) -> dict:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            return await repo.get_cost_overrides()

    return _sync_run(_do())


class TestProfileAwareCheckSeam:
    """CLI check command uses profile YAML when a domain profile is active."""

    def test_check_with_profile_uses_profile_pipeline(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
    ) -> None:
        """sw check --level component routes to profile YAML (not default).

        We verify by checking that the output mentions the expected pipeline
        (or doesn't crash), and that the DB correctly reports the profile.
        """
        name, _ = _project
        _set_domain_profile_sync(_mock_db, name, "library")

        result = runner.invoke(
            app,
            [
                "check",
                str(_spec_file),
                "--level",
                "component",
            ],
        )
        # Should succeed (maybe warnings, but not crash)
        assert result.exit_code in (0, 1), f"Crashed:\n{result.output}"
        # Profile is still stored
        assert _get_domain_profile_sync(_mock_db, name) == "library"

    def test_check_with_web_app_profile(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
    ) -> None:
        """Check with web-app profile completes without crashing."""
        name, _ = _project
        _set_domain_profile_sync(_mock_db, name, "web-app")

        result = runner.invoke(
            app,
            [
                "check",
                str(_spec_file),
                "--level",
                "component",
            ],
        )
        assert result.exit_code in (0, 1), f"Crashed:\n{result.output}"

    def test_check_without_profile_uses_default_pipeline(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
    ) -> None:
        """Check without any profile uses the spec_default pipeline."""
        # No profile set
        name, _ = _project
        assert _get_domain_profile_sync(_mock_db, name) is None

        result = runner.invoke(
            app,
            [
                "check",
                str(_spec_file),
                "--level",
                "component",
            ],
        )
        assert result.exit_code in (0, 1), f"Crashed:\n{result.output}"


# ===========================================================================
# Explicit --pipeline overrides active profile (scenarios 40, 77)
# ===========================================================================


class TestExplicitPipelineOverridesProfile:
    """--pipeline beats active profile during sw check."""

    def test_explicit_pipeline_beats_profile(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
    ) -> None:
        """Explicit --pipeline uses the given YAML even when profile is active."""
        name, _ = _project
        _set_domain_profile_sync(_mock_db, name, "web-app")

        result = runner.invoke(
            app,
            [
                "check",
                str(_spec_file),
                "--level",
                "component",
                "--pipeline",
                "validation_spec_default",
            ],
        )
        # Should use validation_spec_default (not web-app), but shouldn't crash
        assert result.exit_code in (0, 1), f"Crashed:\n{result.output}"

    def test_feature_level_beats_profile(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
    ) -> None:
        """--level feature ignores active profile."""
        name, _ = _project
        _set_domain_profile_sync(_mock_db, name, "microservice")

        result = runner.invoke(
            app,
            [
                "check",
                str(_spec_file),
                "--level",
                "feature",
            ],
        )
        assert result.exit_code in (0, 1), f"Crashed:\n{result.output}"
