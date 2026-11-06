# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which framework a task's code is written for: the folder's archetype, else the build file's."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from specweaver.workflows.implementation.languages import FrameworkGuide, framework_guide

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrameworkChoice:
    """The framework's guide, and where it was found: `archetype` or `build file`."""

    key: str
    guide: FrameworkGuide
    source: str


def project_framework(
    project_root: Path, code_path: Path, language: str, build_framework: str
) -> FrameworkChoice | None:
    """The framework for code at `code_path` in `language`, or None.

    An archetype counts only when a framework file of that name exists and is for `language`;
    otherwise `build_framework`, the profile's framework, decides. Raises `ValueError` for a
    framework file that is incomplete.
    """
    from specweaver.core.config.archetype_resolver import ArchetypeResolver

    archetype = ArchetypeResolver(project_root).resolve(code_path)
    if archetype:
        guide = framework_guide(archetype, project_root)
        if guide is not None and language in guide.languages:
            return FrameworkChoice(archetype, guide, "archetype")
        if guide is not None:
            logger.info(
                "Archetype %r is for %s, not %s: ignored", archetype, guide.languages, language
            )
    guide = framework_guide(build_framework, project_root) if build_framework else None
    return FrameworkChoice(build_framework, guide, "build file") if guide else None
