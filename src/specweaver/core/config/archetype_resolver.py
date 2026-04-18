# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Fractal Resolution Engine for parsing archetype identifiers along repository trees."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

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
        """Walk up the directory tree to find the nearest archetype.

        Args:
            target_path: The file or directory to evaluate.

        Returns:
            The associated archetype string defined in context.yaml, or None if project_root is exceeded.
        """
        current = target_path.resolve()
        seen_paths: list[Path] = []

        while True:
            # Check cache for O(1) resolution
            if current in self._cache:
                archetype = self._cache[current]
                self._backfill_cache(seen_paths, archetype)
                return archetype

            seen_paths.append(current)

            # Look for context.yaml in current dir
            if current.is_dir():
                context_file = current / "context.yaml"
                if context_file.is_file():
                    archetype = self._parse_archetype_from_context(context_file)
                    if archetype is not None:
                        self._backfill_cache(seen_paths, archetype)
                        return archetype

            # Halt boundaries
            if current == self._project_root:
                break

            parent = current.parent
            if parent == current:
                # Reached filesystem OS root without hitting project_root
                break

            current = parent

        # Hit the top without finding anything
        self._backfill_cache(seen_paths, None)
        return None

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
        """Walk up the directory tree to find the nearest context.yaml plugins array.

        Args:
            target_path: The file or directory to evaluate.

        Returns:
            A list of plugin string identifiers defined in context.yaml, or an empty list if none are found.
        """
        current = target_path.resolve()
        seen_paths: list[Path] = []

        while True:
            # Check cache for O(1) resolution
            if current in self._plugin_cache:
                plugins = self._plugin_cache[current]
                self._backfill_plugin_cache(seen_paths, plugins)
                return plugins

            seen_paths.append(current)

            # Look for context.yaml in current dir
            if current.is_dir():
                context_file = current / "context.yaml"
                if context_file.is_file():
                    plugins = self._parse_plugins_from_context(context_file)
                    if plugins is not None:
                        self._backfill_plugin_cache(seen_paths, plugins)
                        return plugins

            # Halt boundaries
            if current == self._project_root:
                break

            parent = current.parent
            if parent == current:
                # Reached filesystem OS root without hitting project_root
                break

            current = parent

        # Hit the top without finding anything
        self._backfill_plugin_cache(seen_paths, [])
        return []

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
