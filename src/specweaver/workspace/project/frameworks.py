# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which framework a file is written for: one answer for generation and validation.

A framework is a name with an evaluator schema (packaged, or the project's
`.specweaver/evaluators/`); the schema's `supported_languages` are its languages, and a schema
naming none covers any file. The answer is the nearest `context.yaml` `framework:`, then an
`archetype:` that names a framework, then the profile's build-file framework, the first one whose
languages cover the file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from specweaver.commons.languages import LANGUAGE_SUFFIXES, language_of

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.commons.project_profile import ProjectProfile

logger = logging.getLogger(__name__)

#: (project root, archetype) pairs already told to move to `framework:`, once per process.
_WARNED: set[tuple[Path, str]] = set()


@dataclass(frozen=True)
class FrameworkAnswer:
    key: str
    #: `framework`, `archetype` or `build file`.
    source: str
    #: Empty when the schema names no language: any file.
    languages: tuple[str, ...]


def framework_for(root: Path, path: Path, profile: ProjectProfile | None) -> FrameworkAnswer | None:
    """The framework of the file at `path` in the project at `root`, or None.

    `profile` None (an undecided root) leaves the build file out. Raises `ValueError` for a schema
    naming a language SpecWeaver does not know.
    """
    from specweaver.core.config.archetype_resolver import ArchetypeResolver
    from specweaver.workspace.project.evaluator_schemas import load_evaluator_schemas

    schemas = load_evaluator_schemas(project_dir=root)
    resolver = ArchetypeResolver(root)
    candidates = (
        ("framework", resolver.resolve_framework(path)),
        ("archetype", resolver.resolve(path)),
        ("build file", profile.framework if profile else None),
    )
    for source, key in candidates:
        if not key:
            continue
        if key not in schemas:
            if source == "framework":
                logger.warning(missing_schema(key))
            continue
        languages = languages_of(key, schemas[key])
        if languages and language_of(path.name) not in languages:
            continue
        if source == "archetype":
            _warn_move(root, key)
        return FrameworkAnswer(key, source, languages)
    return None


def missing_schema(key: str) -> str:
    return (
        f"{key!r} is not a framework: it has no evaluator schema "
        f"(.specweaver/evaluators/{key}.yaml); it is not used"
    )


def languages_of(key: str, schema: dict[str, object]) -> tuple[str, ...]:
    """The languages a framework's schema names; refused, naming them, when one is unknown."""
    metadata = schema.get("metadata")
    named = (metadata.get("supported_languages") if isinstance(metadata, dict) else None) or []
    languages = tuple(str(name) for name in named)
    unknown = sorted(set(languages) - LANGUAGE_SUFFIXES.keys())
    if unknown:
        msg = f"framework {key!r} names unknown languages {unknown}"
        raise ValueError(msg)
    return languages


def _warn_move(root: Path, key: str) -> None:
    if (root, key) in _WARNED:
        return
    _WARNED.add((root, key))
    logger.warning(
        "context.yaml archetype %r names a framework; put it under `framework: %s` instead",
        key,
        key,
    )
