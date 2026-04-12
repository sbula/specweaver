# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for llm/router.py — ModelRouter and RouterResult."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> Any:
    """Fresh in-memory database with full schema."""
    from specweaver.core.config.database import Database

    return Database(tmp_path / ".specweaver" / "specweaver.db")


@pytest.fixture()
def db_with_project(db: Any) -> Any:
    """DB with a registered active project."""
    db.register_project("test-proj", "/tmp/test")
    db.set_active_project("test-proj")
    return db


@pytest.fixture()
def gemini_profile_id(db_with_project: Any) -> int:
    """A gemini LLM profile linked to the test project for 'task:implement'."""
    pid = db_with_project.create_llm_profile(
        "gemini-fast",
        provider="gemini",
        model="gemini-3-flash-preview",
        temperature=0.2,
        max_output_tokens=4096,
    )
    db_with_project.link_project_profile("test-proj", "task:implement", pid)
    return pid


@pytest.fixture()
def gemini_pro_profile_id(db_with_project: Any) -> int:
    """A gemini-pro profile linked for 'task:review' (same provider, different model)."""
    pid = db_with_project.create_llm_profile(
        "gemini-pro",
        provider="gemini",
        model="gemini-2.5-pro-preview-03-25",
        temperature=0.3,
        max_output_tokens=8192,
    )
    db_with_project.link_project_profile("test-proj", "task:review", pid)
    return pid


# ---------------------------------------------------------------------------
# T1 — RouterResult NamedTuple
# ---------------------------------------------------------------------------


class TestRouterResult:
    """RouterResult is a NamedTuple with the correct fields."""

    def test_is_namedtuple(self) -> None:
        """RouterResult can be constructed by position and accessed by name."""
        from specweaver.infrastructure.llm.router import RouterResult

        mock_adapter = MagicMock()
        result = RouterResult(
            adapter=mock_adapter,
            model="gemini-3-flash-preview",
            temperature=0.5,
            max_output_tokens=4096,
            provider="gemini",
            profile_name="my-profile",
        )

        assert result.adapter is mock_adapter
        assert result.model == "gemini-3-flash-preview"
        assert result.temperature == 0.5
        assert result.max_output_tokens == 4096
        assert result.provider == "gemini"
        assert result.profile_name == "my-profile"

    def test_is_tuple_compatible(self) -> None:
        """RouterResult behaves as a tuple (positional unpacking works)."""
        from specweaver.infrastructure.llm.router import RouterResult

        mock_adapter = MagicMock()
        result = RouterResult(mock_adapter, "model-x", 0.7, 2048, "openai", "")
        adapter, model, temp, _max_tok, _provider, _profile = result
        assert adapter is mock_adapter
        assert model == "model-x"
        assert temp == 0.7

    def test_truthy(self) -> None:
        """A RouterResult instance is always truthy (non-empty tuple)."""
        from specweaver.infrastructure.llm.router import RouterResult

        result = RouterResult(MagicMock(), "m", 0.1, 1, "p", "")
        assert bool(result) is True


# ---------------------------------------------------------------------------
# T2 — ModelRouter.get_for_task() — no-routing / error paths
# ---------------------------------------------------------------------------


class TestModelRouterNoRouting:
    """get_for_task() returns None and never raises on error paths."""

    def test_returns_none_when_no_entry_in_db(self, db_with_project: Any) -> None:
        """No routing entry for task_type → returns None (no exception)."""
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter

        router = ModelRouter(db_with_project, "test-proj")
        result = router.get_for_task(TaskType.REVIEW)
        assert result is None

    def test_returns_none_on_load_settings_value_error(self, db_with_project: Any) -> None:
        """ValueError from load_settings (no link) → None, no raise."""
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter

        router = ModelRouter(db_with_project, "test-proj")
        with patch(
            "specweaver.infrastructure.llm.router.load_settings",
            side_effect=ValueError("no link"),
        ):
            result = router.get_for_task(TaskType.IMPLEMENT)
        assert result is None

    def test_returns_none_on_generic_exception(self, db_with_project: Any) -> None:
        """Unexpected exception in load_settings → None, no raise (logged as warning)."""
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter

        router = ModelRouter(db_with_project, "test-proj")
        with patch(
            "specweaver.infrastructure.llm.router.load_settings",
            side_effect=RuntimeError("db exploded"),
        ):
            result = router.get_for_task(TaskType.PLAN)
        assert result is None

    def test_returns_none_on_adapter_creation_failure(
        self, db_with_project: Any, gemini_profile_id: int
    ) -> None:
        """Adapter class raises on construction → None, no raise."""
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter

        router = ModelRouter(db_with_project, "test-proj")
        with patch(
            "specweaver.infrastructure.llm.router.get_adapter_class",
            side_effect=KeyError("unknown provider"),
        ):
            result = router.get_for_task(TaskType.IMPLEMENT)
        assert result is None


# ---------------------------------------------------------------------------
# T3 — ModelRouter.get_for_task() — happy path + adapter caching
# ---------------------------------------------------------------------------


class TestModelRouterHappyPath:
    """get_for_task() returns RouterResult with correct fields."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_returns_router_result_with_correct_fields(
        self, db_with_project: Any, gemini_profile_id: int
    ) -> None:
        """Entry exists → RouterResult with model/temperature/provider from profile."""
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter, RouterResult

        router = ModelRouter(db_with_project, "test-proj")
        result = router.get_for_task(TaskType.IMPLEMENT)

        assert result is not None
        assert isinstance(result, RouterResult)
        assert result.model == "gemini-3-flash-preview"
        assert result.temperature == pytest.approx(0.2)
        assert result.max_output_tokens == 4096
        assert result.provider == "gemini"

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_same_adapter_instance_on_second_call_same_provider(
        self, db_with_project: Any, gemini_profile_id: int
    ) -> None:
        """Two calls for same provider+key → same cached adapter instance."""
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter

        router = ModelRouter(db_with_project, "test-proj")
        r1 = router.get_for_task(TaskType.IMPLEMENT)
        r2 = router.get_for_task(TaskType.IMPLEMENT)

        assert r1 is not None
        assert r2 is not None
        assert r1.adapter is r2.adapter

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_same_provider_different_models_same_adapter_instance(
        self, db_with_project: Any, gemini_profile_id: int, gemini_pro_profile_id: int
    ) -> None:
        """gemini-flash (implement) and gemini-pro (review) share one GeminiAdapter instance."""
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter

        router = ModelRouter(db_with_project, "test-proj")
        r_implement = router.get_for_task(TaskType.IMPLEMENT)
        r_review = router.get_for_task(TaskType.REVIEW)

        assert r_implement is not None
        assert r_review is not None
        # Same adapter (same provider+key) but different models and temperatures
        assert r_implement.adapter is r_review.adapter
        assert r_implement.model == "gemini-3-flash-preview"
        assert r_review.model == "gemini-2.5-pro-preview-03-25"
        assert r_implement.temperature == pytest.approx(0.2)
        assert r_review.temperature == pytest.approx(0.3)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "anthropic-key"})
    def test_different_providers_get_different_adapter_instances(
        self, db_with_project: Any
    ) -> None:
        """gemini + anthropic → two different adapter instances."""
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter

        # Add anthropic profile for PLAN task
        anthropic_id = db_with_project.create_llm_profile(
            "claude-profile",
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            temperature=0.4,
            max_output_tokens=8192,
        )
        db_with_project.link_project_profile("test-proj", "task:plan", anthropic_id)
        # gemini for IMPLEMENT
        gemini_id = db_with_project.create_llm_profile(
            "gemini-fast",
            provider="gemini",
            model="gemini-3-flash-preview",
            temperature=0.2,
            max_output_tokens=4096,
        )
        db_with_project.link_project_profile("test-proj", "task:implement", gemini_id)

        router = ModelRouter(db_with_project, "test-proj")
        r_plan = router.get_for_task(TaskType.PLAN)
        r_implement = router.get_for_task(TaskType.IMPLEMENT)

        assert r_plan is not None
        assert r_implement is not None
        assert r_plan.adapter is not r_implement.adapter
        assert r_plan.provider == "anthropic"
        assert r_implement.provider == "gemini"


# ---------------------------------------------------------------------------
# T4 — ModelRouter.get_for_task() — telemetry wrapping
# ---------------------------------------------------------------------------


class TestModelRouterTelemetry:
    """Telemetry wrapping behaviour."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_no_telemetry_project_returns_raw_adapter(
        self, db_with_project: Any, gemini_profile_id: int
    ) -> None:
        """telemetry_project=None → raw adapter (no TelemetryCollector)."""
        from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter

        router = ModelRouter(db_with_project, "test-proj", telemetry_project=None)
        result = router.get_for_task(TaskType.IMPLEMENT)

        assert result is not None
        assert isinstance(result.adapter, GeminiAdapter)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_telemetry_project_set_wraps_in_collector(
        self, db_with_project: Any, gemini_profile_id: int
    ) -> None:
        """telemetry_project set → adapter is TelemetryCollector."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter

        router = ModelRouter(db_with_project, "test-proj", telemetry_project="test-proj")
        result = router.get_for_task(TaskType.IMPLEMENT)

        assert result is not None
        assert isinstance(result.adapter, TelemetryCollector)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_cached_adapter_not_double_wrapped(
        self, db_with_project: Any, gemini_profile_id: int, gemini_pro_profile_id: int
    ) -> None:
        """Second call for same provider → same already-wrapped adapter (no double-wrap)."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector
        from specweaver.infrastructure.llm.models import TaskType
        from specweaver.infrastructure.llm.router import ModelRouter

        router = ModelRouter(db_with_project, "test-proj", telemetry_project="test-proj")
        r1 = router.get_for_task(TaskType.IMPLEMENT)
        r2 = router.get_for_task(TaskType.REVIEW)

        assert r1 is not None and r2 is not None
        assert r1.adapter is r2.adapter
        # The adapter itself must not be double-wrapped (collector inside collector)
        assert isinstance(r1.adapter, TelemetryCollector)
        assert not isinstance(r1.adapter._adapter, TelemetryCollector)
