# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-02 SF-02 T1: the generic context-provider channel seam (post-TECH-006 shape).

Direct tests: core stays terminal-agnostic — it only asks the registered factory for a
provider and attaches non-None results. The factory owns interactivity (may return None).
R1 (Red/Blue): the module-global factory is reset around every test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.interfaces import cli as flow_cli_mod
from specweaver.core.flow.interfaces.cli import (
    _maybe_attach_provider,
    set_context_provider_factory,
)


@pytest.fixture(autouse=True)
def _reset_factory():
    """R1: never leak the module-global factory across tests."""
    saved = flow_cli_mod._context_provider_factory
    set_context_provider_factory(None)
    yield
    flow_cli_mod._context_provider_factory = saved


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "s_spec.md")


def test_registered_factory_attaches_provider_once(tmp_path) -> None:
    """[Happy] factory returns a provider -> attached; called exactly once."""
    provider = MagicMock(name="provider")
    factory = MagicMock(return_value=provider)
    set_context_provider_factory(factory)

    ctx = _ctx(tmp_path)
    _maybe_attach_provider(ctx)

    assert ctx.context_provider is provider
    factory.assert_called_once()


def test_factory_returning_none_leaves_context_untouched(tmp_path) -> None:
    """[Boundary] delivery says 'not interactive' (None) -> context stays None."""
    set_context_provider_factory(lambda: None)
    ctx = _ctx(tmp_path)
    _maybe_attach_provider(ctx)
    assert ctx.context_provider is None


def test_no_factory_registered_is_inert(tmp_path) -> None:
    """[Boundary] nothing registered -> no-op, no crash."""
    ctx = _ctx(tmp_path)
    _maybe_attach_provider(ctx)
    assert ctx.context_provider is None


def test_existing_provider_never_overwritten_and_factory_not_called(tmp_path) -> None:
    """[Boundary] a caller-supplied provider wins; the factory is not even consulted."""
    factory = MagicMock(return_value=MagicMock())
    set_context_provider_factory(factory)

    ctx = _ctx(tmp_path)
    existing = MagicMock(name="existing")
    ctx.context_provider = existing
    _maybe_attach_provider(ctx)

    assert ctx.context_provider is existing
    factory.assert_not_called()


def test_factory_raising_degrades_to_none(tmp_path) -> None:
    """[Degradation] a channel failure must never break a run."""

    def _boom():
        raise RuntimeError("no console")

    set_context_provider_factory(_boom)
    ctx = _ctx(tmp_path)
    _maybe_attach_provider(ctx)  # must not raise
    assert ctx.context_provider is None
