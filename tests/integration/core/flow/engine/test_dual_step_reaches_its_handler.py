# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The bundled `scenario_integration` pipeline's dual step reaches the dual handler.

Proves: TECH-082 FR-10

The seam: the pipeline loader reads the YAML, the step table accepts the pair, and the real
registry resolves it. Before FR-10 the step was `orchestrate`+`components` with `params.mode`, so
the registry gave the component orchestrator, which then handed the step on.
"""

from __future__ import annotations

from importlib.resources import as_file, files

import pytest

from specweaver.core.flow.engine.parser import load_pipeline
from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

pytestmark = pytest.mark.integration


def test_the_bundled_dual_step_reaches_the_dual_handler() -> None:
    source = files("specweaver.workflows.pipelines").joinpath("scenario_integration.yaml")
    with as_file(source) as path:
        pipeline = load_pipeline(path)

    step = next(s for s in pipeline.steps if s.name == "run_dual_pipelines")
    handler = StepHandlerRegistry().get(step.action, step.target)

    assert isinstance(handler, ArbitrateDualPipelineHandler)
