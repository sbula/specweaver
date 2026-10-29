# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw draft` asks through the channel the shell registers; drafting imports nothing from the shell.

Proves: TECH-081 FR-15

| Bucket | Case |
|---|---|
| Happy | the registered factory's provider is the run's context provider |
| Boundary | with no factory registered the run gets no provider |
| Degradation | a factory that fails stops the command; the error is not hidden |
| Hostile | registering `None` clears an earlier factory |
| Seam | the shell registers a factory that returns its `HITLProvider` |
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.workflows.drafting.interfaces import cli as drafting

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture(autouse=True)
def _restore_factory() -> Iterator[None]:
    before = drafting._hitl_provider_factory
    yield
    drafting.set_hitl_provider_factory(before)


def _draft(tmp_path: Path) -> SimpleNamespace:
    """Run `sw draft` with the run built and run by doubles; the context it ran with."""
    from specweaver.core.flow.engine.state import RunStatus

    context = SimpleNamespace(context_provider=None)
    runner = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(status=RunStatus.COMPLETED))
    )
    with (
        patch("specweaver.interfaces.run_doors.run_doors.build_run_or_exit", return_value=context),
        patch("specweaver.core.flow.engine.runner.PipelineRunner", return_value=runner),
        patch.object(drafting, "_report_draft_chain"),
    ):
        drafting.draft(name="greet", project=str(tmp_path), selector="direct")
    return context


def test_the_registered_factory_gives_the_run_its_provider(tmp_path: Path) -> None:
    provider = object()
    drafting.set_hitl_provider_factory(lambda: provider)

    assert _draft(tmp_path).context_provider is provider


def test_no_factory_means_no_provider(tmp_path: Path) -> None:
    drafting.set_hitl_provider_factory(None)

    assert _draft(tmp_path).context_provider is None


def test_a_failing_factory_stops_the_command(tmp_path: Path) -> None:
    def broken() -> object:
        raise RuntimeError("no terminal")

    drafting.set_hitl_provider_factory(broken)

    with pytest.raises(RuntimeError, match="no terminal"):
        _draft(tmp_path)


def test_registering_none_clears_an_earlier_factory(tmp_path: Path) -> None:
    drafting.set_hitl_provider_factory(object)
    drafting.set_hitl_provider_factory(None)

    assert _draft(tmp_path).context_provider is None


def test_the_shell_registers_its_hitl_provider() -> None:
    import specweaver.interfaces.cli.main  # noqa: F401 - registration happens on import
    from specweaver.interfaces.cli.hitl_provider import HITLProvider

    factory = drafting._hitl_provider_factory
    assert factory is not None
    assert isinstance(factory(), HITLProvider)
