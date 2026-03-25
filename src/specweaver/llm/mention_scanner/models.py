# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Data models for the mention scanner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResolvedMention:
    """A file reference extracted from LLM output and resolved to disk.

    Attributes:
        original: The raw string as it appeared in the LLM response.
        resolved_path: The absolute path to the file on disk.
        kind: Classification — ``"spec"`` | ``"code"`` | ``"test"``
              | ``"config"`` | ``"other"``.
    """

    original: str
    resolved_path: Path
    kind: str

    @classmethod
    def classify(cls, path: Path) -> str:
        """Determine the kind based on file extension and path components.

        Rules:
        - ``.md`` → ``"spec"``
        - ``.py`` in a directory containing ``test`` → ``"test"``
        - ``.py`` → ``"code"``
        - ``.yaml`` / ``.yml`` / ``.json`` / ``.toml`` → ``"config"``
        - Everything else → ``"other"``
        """
        suffix = path.suffix.lower()
        parts_lower = [p.lower() for p in path.parts]

        if suffix == ".md":
            return "spec"
        if suffix == ".py":
            if any("test" in part for part in parts_lower):
                return "test"
            return "code"
        if suffix in {".yaml", ".yml", ".json", ".toml"}:
            return "config"
        return "other"
