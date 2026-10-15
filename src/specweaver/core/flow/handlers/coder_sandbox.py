# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where the coder's code runs: in a container whenever scenario tests must stay out of its reach.

That is the coder side of a dual run, and any run of a project whose store keeps a scenario set.
Every step that runs the coder's code asks this one rule: the test step, C03/C04 and lint fix.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.core.config.settings import SandboxSettings
from specweaver.sandbox.qa_runner.core.atom import container_available

if TYPE_CHECKING:
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def coder_sandbox(context: RunContext) -> SandboxSettings | None:
    """The sandbox settings for a step that runs the coder's code."""
    configured = context.model.config.sandbox if context.model.config else None
    if not (context.run.dual_side == "coder" or _keeps_scenarios(context)):
        return configured
    if container_available(context.project_path):
        return (configured or SandboxSettings()).model_copy(update={"execution_mode": "container"})
    # A dual run has refused already; a normal run goes on, said out loud.
    logger.warning(
        "This project keeps scenario tests, and no container can run its code here, so the "
        "code runs on the host where it could read them. Install Podman or Docker to close that."
    )
    return configured


def _keeps_scenarios(context: RunContext) -> bool:
    from specweaver.core.flow.handlers.scenario import scenario_store

    store = scenario_store(context)
    return store is not None and any((store / "generated").glob("*"))
