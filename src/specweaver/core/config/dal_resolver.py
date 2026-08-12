# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Fractal Resolution Engine for parsing DAL vectors along repository trees."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config._context_walk import resolve_up_tree

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
        """The nearest DAL declared at or above `target_path`, or None.

        Raises:
            ValueError: If a `dal_level` exists but is malformed.
        """
        dal, seen = resolve_up_tree(
            target_path, self._project_root, self._cache, self._parse_dal_from_context
        )
        self._backfill_cache(seen, dal)
        return dal

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
