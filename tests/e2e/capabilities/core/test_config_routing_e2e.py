# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""E2E tests — LLM model routing CLI commands (Feature 3.12b SF-2).

Exercises:
    sw config routing set <task_type> <profile_name>
    sw config routing show
    sw config routing clear
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fixtures.db_utils import set_test_active_project

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database

runner = CliRunner()

_proj_counter = 0


def _unique_name(prefix: str = "test-route") -> str:
    """Generate unique project names to avoid DB collisions."""
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"


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


class TestConfigRoutingE2E:
    """E2E tests for sw config routing commands."""

    def test_full_routing_lifecycle(self, tmp_path: Path, _mock_db: Database) -> None:
        """Full E2E lifecycle: set, show, and clear."""
        name = _unique_name("route-lifecycle")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        set_test_active_project(_mock_db, name)

        # Create some profiles backing the routes
        _create_llm_profile_sync(_mock_db, "o1-mini-prof", provider="openai", model="o1-mini")
        _create_llm_profile_sync(
            _mock_db,
            "claude-prof",
            provider="anthropic",
            model="claude-3-5-sonnet",
        )

        # 1. SET
        result = runner.invoke(app, ["config", "routing", "set", "plan", "o1-mini-prof"])
        assert result.exit_code == 0
        assert "plan" in result.output
        assert "o1-mini-prof" in result.output

        result2 = runner.invoke(app, ["config", "routing", "set", "implement", "claude-prof"])
        assert result2.exit_code == 0

        # 2. SHOW
        show_result = runner.invoke(app, ["config", "routing", "show"])
        assert show_result.exit_code == 0
        assert "plan" in show_result.output
        assert "o1-mini-prof" in show_result.output
        assert "implement" in show_result.output
        assert "claude-prof" in show_result.output

        # 3. CLEAR specific
        clear_spec = runner.invoke(app, ["config", "routing", "clear", "plan"])
        assert clear_spec.exit_code == 0
        assert "Cleared routing for" in clear_spec.output
        assert "plan" in clear_spec.output

        # 4. SHOW after clear specific (plan is gone, implement remains)
        show_result2 = runner.invoke(app, ["config", "routing", "show"])
        assert "plan" not in show_result2.output
        assert "implement" in show_result2.output

        # 5. CLEAR all
        # By default 'clear' doesn't ask for confirmation right now (unless I add a prompt), wait in test CLI we didn't add prompt
        clear_all = runner.invoke(app, ["config", "routing", "clear"])
        assert clear_all.exit_code == 0
        assert "Cleared all" in clear_all.output

        # 6. SHOW after clear all
        show_result3 = runner.invoke(app, ["config", "routing", "show"])
        assert "No routing configured" in show_result3.output

    def test_show_orphaned_profile(self, tmp_path: Path, _mock_db: Database) -> None:
        """If a profile is deleted, 'show' renders it safely."""
        name = _unique_name("route-orphan")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        set_test_active_project(_mock_db, name)

        pid = _create_llm_profile_sync(
            _mock_db, "doomed-prof", provider="gemini", model="gemini-1.5-pro"
        )
        runner.invoke(app, ["config", "routing", "set", "review", "doomed-prof"])

        # Orphan the profile by deleting the underlying profile ID
        with _mock_db.connect() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM llm_profiles WHERE id = ?", (pid,))
            conn.execute("PRAGMA foreign_keys = ON")

        show_result = runner.invoke(app, ["config", "routing", "show"])
        assert show_result.exit_code == 0
        assert "review" in show_result.output
        assert "[deleted]" in show_result.output

    def test_invalid_terminal_inputs(self, tmp_path: Path, _mock_db: Database) -> None:
        """Invalid commands exit gracefully with non-zero exit codes."""
        name = _unique_name("route-invalid")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        set_test_active_project(_mock_db, name)

        # 1. Invalid task type
        res1 = runner.invoke(app, ["config", "routing", "set", "fly", "some-prof"])
        assert res1.exit_code != 0

        # 2. Nonexistent profile
        res2 = runner.invoke(app, ["config", "routing", "set", "draft", "nonexistent-prof"])
        assert res2.exit_code != 0
        assert "Profile 'nonexistent-prof' not found" in res2.output
