# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The DAL a run's target is held to."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.commons.enums.dal import DALLevel
    from specweaver.core.flow.run_state.run_context import RunContext


def target_dal(context: RunContext, target_path: Path) -> DALLevel:
    """The target's DAL: its nearest `context.yaml`, else its project's default, else `DAL_C`."""
    from specweaver.core.config.dal_resolver import DALResolver
    from specweaver.core.flow.run_state.registered import registered
    from specweaver.workspace.store import DEFAULT_DAL, default_dal_at

    dal = DALResolver(context.project_path).resolve(target_path)
    if dal is None:
        dal = registered(context, default_dal_at, "default DAL")
    return dal or DEFAULT_DAL
