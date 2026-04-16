# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Fractal Resolution Engine for parsing DAL vectors along repository trees."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from specweaver.commons.enums.dal import DALLevel

if TYPE_CHECKING:
    from pathlib import Path


class DALResolver:
    """O(1) Cached Directory-Tree Walker for Design Assurance Levels."""

    def __init__(self, project_root: Path) -> None:
        """Initialize resolver bounded to a strict project root.

        Args:
            project_root: The root boundary of the project repository.
        """
        self._project_root = project_root.resolve()
        self._cache: dict[Path, DALLevel | None] = {}

    def resolve(self, target_path: Path) -> DALLevel | None:
        """Walk up the directory tree to find the nearest DAL.

        Args:
            target_path: The file or directory to evaluate.

        Returns:
            The associated DALLevel, or None if project_root is exceeded.

        Raises:
            ValueError: If a dal_level exists but is malformed.
        """
        current = target_path.resolve()
        seen_paths: list[Path] = []

        while True:
            # Check cache for O(1) resolution
            if current in self._cache:
                dal = self._cache[current]
                self._backfill_cache(seen_paths, dal)
                return dal

            seen_paths.append(current)

            # Look for context.yaml in current dir
            if current.is_dir():
                context_file = current / "context.yaml"
                if context_file.is_file():
                    dal = self._parse_dal_from_context(context_file)
                    if dal is not None:
                        self._backfill_cache(seen_paths, dal)
                        return dal

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

    def _backfill_cache(self, paths: list[Path], dal: DALLevel | None) -> None:
        """Populate the cache for all intermediate paths walked."""
        for path in paths:
            self._cache[path] = dal

    def _parse_dal_from_context(self, context_file: Path) -> DALLevel | None:
        """Parse the operational.dal_level from a context.yaml file."""
        try:
            with context_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return None

        op = data.get("operational", {})
        if not isinstance(op, dict):
            return None

        dal_str = op.get("dal_level")
        if dal_str is None:
            return None

        try:
            return DALLevel(dal_str)
        except ValueError as exc:
            raise ValueError(f"{dal_str} is not a valid DALLevel") from exc
