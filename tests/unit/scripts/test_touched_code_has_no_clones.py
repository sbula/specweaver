# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The code `TECH-090` touched carries no known clone; one import-only pair stays by decision.

The duplication gate stops a new clone anywhere; this test holds the removed ones to zero in the
files the ticket named, so a clone frozen back into the baseline fails here.

Proves: TECH-090 FR-14
"""

from __future__ import annotations

import json
from pathlib import Path

_BASELINE = Path(__file__).resolve().parents[3] / "scripts" / "baselines" / "duplication.json"

_FILES = (
    "src/specweaver/workspace/store.py",
    "src/specweaver/workspace/memory/store.py",
    "src/specweaver/core/flow/store.py",
    "src/specweaver/graph/lineage/store/lineage_repository.py",
    "src/specweaver/interfaces/api/v1/pipelines.py",
    "src/specweaver/interfaces/api/v1/projects.py",
    "src/specweaver/core/flow/engine/display.py",
    "src/specweaver/interfaces/api/event_bridge.py",
)

#: Module header and imports, no code; kept by the user's decision 2026-11-07 (FR-14).
_KEPT = {
    frozenset(
        {
            "src/specweaver/interfaces/api/v1/constitution.py",
            "src/specweaver/interfaces/api/v1/standards.py",
        }
    )
}


def _clones() -> list[dict[str, object]]:
    return list(json.loads(_BASELINE.read_text(encoding="utf-8")).values())


def _pair(clone: dict[str, object]) -> frozenset[str]:
    return frozenset(str(clone[end]).rsplit(":", 1)[0] for end in ("first", "second"))


def test_the_baseline_is_read() -> None:
    assert _clones()


def test_no_touched_file_carries_a_clone() -> None:
    found = [sorted(_pair(c)) for c in _clones() if _pair(c) & set(_FILES)]

    assert found == []


def test_only_the_kept_pair_remains_among_the_api_routes() -> None:
    routes = [_pair(c) for c in _clones() if any("interfaces/api/v1/" in f for f in _pair(c))]

    assert set(routes) <= _KEPT
