# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

from specweaver.core.flow.handlers.base import AnalysisContext, RunContext


def test_run_context_accepts_analyzer_factory():
    """The injected factory now arrives via `analysis`. The guarantee is unchanged: what the
    caller passes in is the very object a handler reads back."""
    dummy_factory = object()
    context = RunContext(
        project_path=Path("/tmp/proj"),
        spec_path=Path("/tmp/proj/spec.md"),
        analysis=AnalysisContext(analyzer_factory=dummy_factory),
    )
    assert context.analysis.analyzer_factory is dummy_factory
