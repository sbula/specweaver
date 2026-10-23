# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The name a run records for its project: the registered one, not the folder's."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def registered_name(context: RunContext) -> str:
    """The name the run's project is registered under; its folder's name when none is found.

    A resume (`POST /runs/{id}/gate`, `sw resume`) finds the project by this name, so a folder
    name here strands every run of a project named unlike its folder.
    """
    from specweaver.core.flow.engine.registered import registered
    from specweaver.workspace.store import project_name_at

    return registered(context, project_name_at, "registered name") or context.project_path.name
