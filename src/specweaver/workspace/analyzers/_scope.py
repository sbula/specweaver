# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a chunk sits, and what access level it carries.

Split out of `chunking.py` on 2026-08-27 with `_sizing.py`, when that file passed the 600-line
ceiling. These answer *which boundary is this inside* and *what may see it* — questions about the
file and the estate, not about where the cuts fall.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def directory_of(path: str) -> str:
    """The directory part of a path, on either platform's separator.

    Not `pathlib`: it resolves against the platform running the scan, so a Windows path handed to a
    Linux worker would come back whole and the chunk would claim the entire path as its package.
    A scan reads paths as data, so they are split as data.
    """
    cut = max(path.rfind("/"), path.rfind("\\"))
    return path[:cut] if cut > 0 else ""


def unit_of(path: str, markers: frozenset[str]) -> str:
    """The nearest ancestor directory the caller marked as a build unit, or `""`.

    **Nearest, not first.** A repository root and a nested package both hold a manifest, and the
    file belongs to the inner one — taking any match would put every file in the repo root.

    Matching is on a path **boundary**, so `src/apple` is not a unit of `src/app/mod`.
    """
    best = ""
    # `sorted`, not the set's own order. A frozenset iterates by hash, which is stable within one
    # process and not across runs -- so two candidates of equal length would tie differently on
    # different days, and `NFR-4` says the same input gives the same chunks. Added when two mutants
    # came back SILENT: an order-dependent implementation cannot be pinned by a deterministic test.
    #
    # Sorting is on the MARKER PATHS, so `src/app/build.gradle` precedes `src/app/mod/go.mod` while
    # `src/app/pyproject.toml` follows it. Length is what decides; the sort only makes which
    # candidate is seen first a fact rather than a coin toss.
    for marker in sorted(markers):
        directory = directory_of(marker)
        if not directory:
            continue
        # On a path BOUNDARY: a bare prefix would make `src/app` a unit of `src/application`.
        if any(path.startswith(directory + sep) for sep in ("/", "\\")) and len(directory) > len(
            best
        ):
            best = directory
    return best


def levels_of(code: str, parser: Any, order: list[str]) -> dict[str, str] | None:
    """Each symbol's access level, or **None when the parser could not answer**.

    `extract_symbol_visibility` re-parses the file every time it is asked, so asking per symbol is
    one parse per symbol — a thousand of them for a thousand-symbol file. `list_symbols` answers a
    whole level at once, and `VISIBILITY` is closed, so the cost is a constant.

    A symbol whose language cannot say arrives in the `public` bucket and is recorded as public.
    That is `AD-5` — `unknown` counts as visible — applied to merging rather than restated.

    **`None` rather than a dict of `unknown`, and the difference is the whole point.** Every symbol
    reading `unknown` means every symbol matches every other, so a private one merges into a public
    chunk — `FR-2`'s filter undone one layer up, failing in the same direction the original defect
    failed. Not knowing is not the same as knowing they are alike. Found by a retrospective
    red/blue on 2026-08-26, on a path no mutant could reach because no line was written for it.
    """
    levels: dict[str, str] = {}
    for level in ("public", "protected", "internal", "private"):
        try:
            for name in parser.list_symbols(code, visibility=[level]):
                levels.setdefault(name, level)
        except Exception:
            logger.debug("Chunking: visibility unavailable at %r; merging disabled", level)
            return None
    return {name: levels.get(name, "unknown") for name in order}
