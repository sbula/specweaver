# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Fractal Resolution Engine for parsing archetype identifiers along repository trees."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from specweaver.core.config._context_walk import resolve_up_tree

if TYPE_CHECKING:
    from pathlib import Path


class ArchetypeResolver:
    """O(1) Cached Directory-Tree Walker for Execution Archetypes."""

    def __init__(self, project_root: Path) -> None:
        """Initialize resolver bounded to a strict project root.

        Args:
            project_root: The root boundary of the project repository.
        """
        self._project_root = project_root.resolve()
        self._cache: dict[Path, str | None] = {}
        self._plugin_cache: dict[Path, list[str]] = {}

    def resolve(self, target_path: Path) -> str | None:
        """The nearest archetype declared at or above `target_path`, or None."""
        archetype, seen = resolve_up_tree(
            target_path, self._project_root, self._cache, self._parse_archetype_from_context
        )
        self._backfill_cache(seen, archetype)
        return archetype

    def _backfill_cache(self, paths: list[Path], archetype: str | None) -> None:
        """Populate the cache for all intermediate paths walked."""
        for path in paths:
            self._cache[path] = archetype

    def _parse_archetype_from_context(self, context_file: Path) -> str | None:
        """Parse the archetype string from a context.yaml file."""
        try:
            with context_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return None

        if not isinstance(data, dict):
            return None

        archetype = data.get("archetype")
        if archetype is None:
            return None

        return str(archetype).strip()

    def resolve_plugins(self, target_path: Path) -> list[str]:
        """The nearest `plugins` array declared at or above `target_path`, else empty."""
        plugins, seen = resolve_up_tree(
            target_path, self._project_root, self._plugin_cache, self._parse_plugins_from_context
        )
        resolved = plugins if plugins is not None else []
        self._backfill_plugin_cache(seen, resolved)
        return resolved

    def _backfill_plugin_cache(self, paths: list[Path], plugins: list[str]) -> None:
        """Populate the plugin cache for all intermediate paths walked."""
        for path in paths:
            self._plugin_cache[path] = plugins

    def _parse_plugins_from_context(self, context_file: Path) -> list[str] | None:
        """Parse the plugins array from a context.yaml file. Returns None if key is missing."""
        try:
            with context_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return None

        if not isinstance(data, dict):
            return None

        if "plugins" not in data:
            return None

        plugins = data.get("plugins")
        if not isinstance(plugins, list):
            return []

        return [str(p).strip() for p in plugins if str(p).strip()]
