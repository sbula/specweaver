# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The files changed since the hash cache was saved, compared file by file.

A boundary's hash covers every file below it, nested boundaries included, so two whole hashes only
say that something below changed. The cache keeps each file's hash; this compares those.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def changed_files(project_root: Path, code_root: Path, boundaries: list[str]) -> set[str] | None:
    """Paths, from the root, of files changed since the cache was saved; None without a cache.

    `project_root` holds the cache; `code_root` holds the code to compare, a worktree when there
    is one. `boundaries` are the module folders, from the root (`.` for the root itself).
    """
    from specweaver.assurance.graph.hasher import DependencyHasher
    from specweaver.workspace.analyzers.factory import AnalyzerFactory

    cache = DependencyHasher(project_root, AnalyzerFactory).load_cache()
    if not cache:
        return None
    now = DependencyHasher(code_root, AnalyzerFactory).compute_hashes(
        [code_root / key / "context.yaml" for key in boundaries]
    )
    try:
        return {f for key in boundaries for f in _changed_under(key, cache, now)}
    except (KeyError, TypeError, ValueError):
        logger.warning("The hash cache cannot be read; it is treated as missing")
        return None


def _changed_under(key: str, old: dict[str, Any], new: dict[str, Any]) -> set[str]:
    """Paths, from the root, of the files that differ under one boundary."""
    before = _payload(old.get(key))
    after = _payload(new.get(key))
    prefix = "" if key == "." else f"{key}/"
    changed = {
        prefix + path
        for path in before["files"].keys() | after["files"].keys()
        if before["files"].get(path) != after["files"].get(path)
    }
    if before["dependencies"] != after["dependencies"]:
        changed.add(prefix + "context.yaml")
    return changed


def _payload(entry: dict[str, Any] | None) -> dict[str, Any]:
    if entry is None:
        return {"files": {}, "dependencies": []}
    payload: dict[str, Any] = json.loads(entry["rendered_payload"])
    return payload
