# mypy: ignore-errors
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
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
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
def _loaded(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record which pipeline YAML `sw check` actually loads, without changing what it does.

    A **spy, not a mock**: the real `load_pipeline_yaml` still runs, so the round-trip this file
    claims to exercise stays real and the recorded name is the one validation actually used.

    This exists because every test below used to assert `exit_code in (0, 1)` — which accepts
    success AND failure — under docstrings claiming the profile pipeline was selected. One even
    said so out loud: *"We verify by checking that the output mentions the expected pipeline (or
    doesn't crash)"*. Nothing mentions it; `_build_result_label` prints "Spec" unless `--pipeline`
    was passed explicitly, so the selected name is invisible in the output and the tests were
    passing on the parenthesis. `TECH-017`.
    """
    from specweaver.assurance.validation import pipeline_loader

    seen: list[str] = []
    real = pipeline_loader.load_pipeline_yaml

    def _spy(name: str, **kwargs: object) -> object:
        seen.append(name)
        return real(name, **kwargs)

    monkeypatch.setattr(pipeline_loader, "load_pipeline_yaml", _spy)
    return seen


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


import anyio  # noqa: E402


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


from specweaver.commons.async_bridge import run_sync  # noqa: E402


def _sync_run(coro):
    """Run a coroutine from a sync test helper without re-entering a running loop.

    Previously applied `nest_asyncio` to the caller's loop. See `commons.async_bridge`.
    """
    return run_sync(lambda: coro)


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
    """CLI check command uses profile YAML when a domain profile is active.

    Every test here asserts **which pipeline was loaded**, not merely that the command survived.
    `TECH-017`: `exit_code in (0, 1)` accepts a pass and a failure alike, so it cannot distinguish
    "the profile selected the library pipeline" from "the profile was ignored entirely".
    """

    def test_check_with_profile_uses_profile_pipeline(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
        _loaded: list[str],
    ) -> None:
        """An active `library` profile routes `--level component` to the library YAML."""
        name, _ = _project
        _set_domain_profile_sync(_mock_db, name, "library")

        runner.invoke(app, ["check", str(_spec_file), "--level", "component"])

        assert _loaded[0] == "validation_spec_library"
        # `validation_spec_library.yaml` carries `extends: validation_spec_default`, so the base is
        # loaded second. Asserted rather than tolerated: it pins that inheritance actually resolves
        # at this seam, which nothing else here proved.
        assert _loaded == ["validation_spec_library", "validation_spec_default"]

    def test_check_with_web_app_profile(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
        _loaded: list[str],
    ) -> None:
        """A second profile proves the mapping varies with the profile, not a constant."""
        name, _ = _project
        _set_domain_profile_sync(_mock_db, name, "web-app")

        runner.invoke(app, ["check", str(_spec_file), "--level", "component"])

        assert _loaded[0] == "validation_spec_web_app"
        assert _loaded == ["validation_spec_web_app", "validation_spec_default"]

    def test_check_without_profile_uses_default_pipeline(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
        _loaded: list[str],
    ) -> None:
        """No profile -> the default YAML. The control for the two tests above."""
        name, _ = _project
        assert _get_domain_profile_sync(_mock_db, name) is None

        runner.invoke(app, ["check", str(_spec_file), "--level", "component"])

        # The default extends nothing, so exactly one load — the control that makes the two
        # tests above meaningful rather than a description of whatever happened.
        assert _loaded == ["validation_spec_default"]

    def test_the_profile_survives_the_check(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
    ) -> None:
        """The DB read that used to be this file's only real assertion, kept as its own test.

        It proves the profile was *written*, which is worth keeping — but it was never evidence
        that the profile *did* anything, and standing beside an `exit_code in (0, 1)` it read as if
        it were.
        """
        name, _ = _project
        _set_domain_profile_sync(_mock_db, name, "library")

        runner.invoke(app, ["check", str(_spec_file), "--level", "component"])

        assert _get_domain_profile_sync(_mock_db, name) == "library"


# ===========================================================================
# Explicit --pipeline overrides active profile (scenarios 40, 77)
# ===========================================================================


class TestExplicitPipelineOverridesProfile:
    """--pipeline beats active profile during sw check.

    Both tests here name a profile whose pipeline is DIFFERENT from the expected winner, so a
    regression that ignored the override would load the profile's YAML and fail the assertion.
    """

    def test_explicit_pipeline_beats_profile(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
        _loaded: list[str],
    ) -> None:
        """`--pipeline` wins over an active `web-app` profile."""
        name, _ = _project
        _set_domain_profile_sync(_mock_db, name, "web-app")

        runner.invoke(
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

        assert _loaded == ["validation_spec_default"]
        assert "validation_spec_web_app" not in _loaded

    def test_feature_level_beats_profile(
        self,
        _project: tuple[str, Path],
        _mock_db: MagicMock,
        _spec_file: Path,
        _loaded: list[str],
    ) -> None:
        """`--level feature` wins over an active `microservice` profile."""
        name, _ = _project
        _set_domain_profile_sync(_mock_db, name, "microservice")

        runner.invoke(app, ["check", str(_spec_file), "--level", "feature"])

        assert _loaded[0] == "validation_spec_feature"
        assert _loaded == ["validation_spec_feature", "validation_spec_default"]
        assert "validation_spec_microservice" not in _loaded
