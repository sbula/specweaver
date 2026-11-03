# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which framework a task's code is written for: the folder's archetype, else the build file."""

from __future__ import annotations

import json
import logging
import re
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from specweaver.workflows.implementation.languages import FrameworkGuide, framework_guide

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

#: In order: the first build-file pattern found names the framework, so Spring Boot is tried
#: before plain Spring.
_JVM_RULES = (
    ("quarkus", "io.quarkus"),
    ("spring-boot", "spring-boot"),
    ("spring-boot", "org.springframework.boot"),
    ("spring", "org.springframework"),
)
_JVM_BUILDS = ("pom.xml", "build.gradle", "build.gradle.kts")
_FASTAPI = re.compile(r"\bfastapi\b", re.IGNORECASE)


@dataclass(frozen=True)
class FrameworkChoice:
    """The framework's guide, and where it was found: `archetype` or `build file`."""

    key: str
    guide: FrameworkGuide
    source: str


def project_framework(project_root: Path, code_path: Path, language: str) -> FrameworkChoice | None:
    """The framework for code at `code_path` in `language`, or None.

    An archetype counts only when a framework file of that name exists and is for `language`;
    otherwise the build file decides. Raises `ValueError` for a framework file that is incomplete.
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
    key = _detected(project_root, language)
    guide = framework_guide(key, project_root) if key else None
    return FrameworkChoice(key, guide, "build file") if key and guide else None


def _detected(project_root: Path, language: str) -> str | None:
    detect = _DETECTORS.get("jvm" if language in {"java", "kotlin"} else language)
    return detect(project_root) if detect else None


def _jvm(project_root: Path) -> str | None:
    text = " ".join(_read(project_root / name) for name in _JVM_BUILDS)
    return next((key for key, mark in _JVM_RULES if mark in text), None)


def _nest(project_root: Path) -> str | None:
    return "nestjs" if "@nestjs/core" in _package_dependencies(project_root) else None


def _actix(project_root: Path) -> str | None:
    return "actix-web" if "actix-web" in _cargo_dependencies(project_root) else None


def _fastapi(project_root: Path) -> str | None:
    sources = [project_root / "pyproject.toml", *sorted(project_root.glob("requirements*.txt"))]
    return "fastapi" if any(_FASTAPI.search(_read(path)) for path in sources) else None


_DETECTORS = {"jvm": _jvm, "typescript": _nest, "rust": _actix, "python": _fastapi}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:  # expected: a missing build file names no framework
        return ""


def _package_dependencies(project_root: Path) -> set[str]:
    try:
        manifest = json.loads(_read(project_root / "package.json") or "{}")
    except ValueError:  # expected: an unreadable manifest names no framework
        return set()
    if not isinstance(manifest, dict):
        return set()
    return {
        name for key in ("dependencies", "devDependencies") for name in (manifest.get(key) or {})
    }


def _cargo_dependencies(project_root: Path) -> set[str]:
    try:
        manifest = tomllib.loads(_read(project_root / "Cargo.toml"))
    except tomllib.TOMLDecodeError:  # expected: an unreadable manifest names no framework
        return set()
    dependencies = manifest.get("dependencies")
    return set(dependencies) if isinstance(dependencies, dict) else set()
