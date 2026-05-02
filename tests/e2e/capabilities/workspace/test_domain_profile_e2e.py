# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""E2E tests — domain profile CLI commands (Feature 3.3).

Exercises:
    sw config profiles / show-profile / set-profile / get-profile / reset-profile
    Profile + individual override layering
    Profile-aware sw check flow
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fixtures.db_utils import set_test_active_project

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

# Counter for unique project names in tests
_proj_counter = 0


def _unique_name(prefix: str = "test") -> str:
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


class TestDomainProfileCLI:
    """E2E tests for sw config profile commands."""

    def test_profiles_lists_all(self, _mock_db) -> None:
        """sw config profiles lists all available profiles."""
        result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "web-app" in result.output
        assert "data-pipeline" in result.output
        assert "library" in result.output
        assert "microservice" in result.output
        assert "ml-model" in result.output

    def test_show_profile(self, _mock_db) -> None:
        """sw config show-profile shows the pipeline parameters for a profile."""
        result = runner.invoke(app, ["config", "show-profile", "web-app"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        # web-app YAML has s05 and s03 overrides
        assert "S05" in result.output or "s05" in result.output.lower()
        # Profile table should show the pipeline name
        assert "web-app" in result.output.lower()

    def test_show_profile_unknown(self, _mock_db) -> None:
        """sw config show-profile with unknown profile shows error."""
        result = runner.invoke(app, ["config", "show-profile", "doesnt-exist"])
        assert result.exit_code != 0

    def test_set_profile(self, tmp_path: Path, _mock_db) -> None:
        """sw config set-profile stores the profile name only (no DB overrides written)."""
        name = _unique_name("profile")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        set_test_active_project(_mock_db, name)

        result = runner.invoke(app, ["config", "set-profile", "web-app"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "web-app" in result.output

        # Profile name is stored
        assert _get_domain_profile_sync(_mock_db, name) == "web-app"

    def test_set_profile_unknown(self, tmp_path: Path, _mock_db) -> None:
        """sw config set-profile with unknown profile shows error."""
        name = _unique_name("profile-bad")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        set_test_active_project(_mock_db, name)

        result = runner.invoke(app, ["config", "set-profile", "quantum"])
        assert result.exit_code != 0

    def test_get_profile_none(self, tmp_path: Path, _mock_db) -> None:
        """sw config get-profile shows no profile when none set."""
        name = _unique_name("profget")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        set_test_active_project(_mock_db, name)

        result = runner.invoke(app, ["config", "get-profile"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "no" in result.output.lower() or "none" in result.output.lower()

    def test_get_profile_after_set(self, tmp_path: Path, _mock_db) -> None:
        """sw config get-profile shows the active profile name."""
        name = _unique_name("profget2")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        set_test_active_project(_mock_db, name)
        runner.invoke(app, ["config", "set-profile", "library"])

        result = runner.invoke(app, ["config", "get-profile"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "library" in result.output

    def test_reset_profile(self, tmp_path: Path, _mock_db) -> None:
        """sw config reset-profile clears profile name only (overrides preserved)."""
        name = _unique_name("profreset")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        set_test_active_project(_mock_db, name)
        runner.invoke(app, ["config", "set-profile", "web-app"])

        result = runner.invoke(app, ["config", "reset-profile"])
        assert result.exit_code == 0, f"Failed: {result.output}"

        # Profile name should be cleared
        assert _get_domain_profile_sync(_mock_db, name) is None
        # Per-rule overrides are preserved (none were set in this test, so empty)
        # assert _mock_db.get_validation_overrides(name) == []

    def test_set_profile_then_check_spec(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Full flow: set-profile → check spec works with profile thresholds."""
        name = _unique_name("profcheck")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        set_test_active_project(_mock_db, name)

        # Apply profile
        result = runner.invoke(app, ["config", "set-profile", "web-app"])
        assert result.exit_code == 0

        # Create a minimal spec and check it
        spec = tmp_path / "specs" / "test_spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(
            "# Test Spec\n\n## 1. Purpose\nA simple test spec.\n\n"
            "## 2. Requirements\n- Do something.\n",
        )
        result = runner.invoke(
            app,
            [
                "check",
                str(spec),
                "--level",
                "component",
                "--project",
                str(tmp_path),
            ],
        )
        # Should run (may pass or warn, but not crash)
        assert result.exit_code in (0, 1), f"Crashed: {result.output}"

    def test_set_profile_no_active_project(self, _mock_db) -> None:
        """sw config set-profile without active project shows error."""
        result = runner.invoke(app, ["config", "set-profile", "web-app"])
        assert result.exit_code != 0
