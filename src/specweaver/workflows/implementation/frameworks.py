# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which framework a task's code is written for, and the guide the model is given for it."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from specweaver.workflows.implementation.languages import FrameworkGuide, framework_guide

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.commons.project_profile import ProjectProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrameworkChoice:
    """The framework's guide, and where it was found: `framework`, `archetype` or `build file`."""

    key: str
    guide: FrameworkGuide
    source: str


def project_framework(
    project_root: Path, code_path: Path, profile: ProjectProfile
) -> FrameworkChoice | None:
    """The framework for code at `code_path`, with its guide; None without one.

    The answer is `workspace.project.framework_for`'s, the one validation uses. A name with a guide
    but no evaluator schema is not a framework; a warning names the missing schema. Raises
    `ValueError` for a framework file that is incomplete.
    """
    from specweaver.core.config.archetype_resolver import ArchetypeResolver
    from specweaver.workspace.project.frameworks import framework_for, missing_schema

    answer = framework_for(project_root, code_path, profile)
    if answer is None:
        archetype = ArchetypeResolver(project_root).resolve(code_path)
        if archetype and framework_guide(archetype, project_root) is not None:
            logger.warning(missing_schema(archetype))
        return None
    guide = framework_guide(answer.key, project_root)
    return FrameworkChoice(answer.key, guide, answer.source) if guide else None
