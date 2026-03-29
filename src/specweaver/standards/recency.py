# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Recency weighting utilities for standards analysis.

Provides exponential decay weighting based on file modification time,
so that recent code conventions are weighted more heavily than legacy patterns.

Usage::

    from specweaver.context.recency import recency_weight, compute_half_life

    half_life = compute_half_life(project_path)
    weight = recency_weight(file.stat().st_mtime, half_life)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# Extensions considered as "source files" for project age estimation.
_SOURCE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".kt",
        ".kts",  # Kotlin
        ".rs",  # Rust
        ".go",  # Go
        ".java",  # Java
        ".rb",  # Ruby
        ".cpp",
        ".c",
        ".h",
        ".hpp",  # C/C++
        ".cs",  # C#
        ".swift",  # Swift
    }
)

# Half-life bounds (days).
_MIN_HALF_LIFE = 180  # 6 months — young/fast-moving projects
_MAX_HALF_LIFE = 730  # 2 years — legacy/stable projects
_HALF_LIFE_SCALE = 120  # days of half-life per year of project age


def recency_weight(file_mtime: float, half_life_days: float) -> float:
    """Compute exponential decay weight based on file modification time.

    Weight = 2^(-age_days / half_life_days)

    - File modified now → weight ≈ 1.0
    - File modified one half-life ago → weight ≈ 0.5
    - File modified two half-lives ago → weight ≈ 0.25

    Args:
        file_mtime: File modification time as a Unix timestamp.
        half_life_days: Decay half-life in days. Must be > 0.

    Returns:
        Weight in (0.0, 1.0].

    Raises:
        ValueError: If ``half_life_days`` is not positive.
    """
    if half_life_days <= 0:
        msg = f"half_life_days must be positive, got {half_life_days}"
        raise ValueError(msg)

    age_days = (time.time() - file_mtime) / 86400
    if age_days < 0:
        age_days = 0  # Future mtime (clock skew) → treat as now

    return 2 ** (-age_days / half_life_days)


def compute_half_life(project_path: Path) -> float:
    """Auto-compute decay half-life from project age.

    Uses the oldest source file's modification time to estimate
    project age.  Applies a linear formula clamped to
    [180, 730] days:

        half_life = min(730, max(180, project_age_years * 120))

    - Young project (< 1.5 years): 180 days (6 months)
    - Mid-age project (5 years): ~600 days
    - Legacy project (30+ years): 730 days (2 years, capped)

    Args:
        project_path: Root directory of the project.

    Returns:
        Half-life in days.
    """
    oldest_mtime = _find_oldest_source_mtime(project_path)
    if oldest_mtime is None:
        return _MIN_HALF_LIFE  # No source files → use minimum

    project_age_days = (time.time() - oldest_mtime) / 86400
    project_age_years = project_age_days / 365

    raw_half_life = project_age_years * _HALF_LIFE_SCALE
    return min(_MAX_HALF_LIFE, max(_MIN_HALF_LIFE, raw_half_life))


def _find_oldest_source_mtime(directory: Path) -> float | None:
    """Find the oldest source file modification time in a directory tree.

    Only considers files with extensions in ``_SOURCE_EXTENSIONS``.
    Walks subdirectories recursively but skips hidden directories
    and ``__pycache__``.

    Returns:
        The oldest mtime as a Unix timestamp, or None if no source files found.
    """
    oldest: float | None = None

    for child in directory.rglob("*"):
        if not child.is_file():
            continue
        if child.suffix.lower() not in _SOURCE_EXTENSIONS:
            continue
        if any(p.startswith(".") or p == "__pycache__" for p in child.parts):
            continue

        mtime = child.stat().st_mtime
        if oldest is None or mtime < oldest:
            oldest = mtime

    return oldest
