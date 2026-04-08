# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SpecKind enum and presets — spec-kind-aware threshold overrides.

SpecKind distinguishes Feature Specs (value-driven, business-level) from
Component Specs (structure-driven, architecture-level).  Rules that change
behaviour based on spec kind query ``get_presets(rule_id, kind)`` for the
appropriate constructor kwargs.

See: docs/proposals/roadmap/phase_3/feature_3_1_implementation_plan.md §4-5.
"""

from __future__ import annotations

import enum
import re


class SpecKind(enum.StrEnum):
    """Type of specification being processed.

    Two orthogonal values:
    - FEATURE:   value-axis spec (business feature or NFR).
    - COMPONENT: structure-axis spec (architectural unit — the default).

    Architecture granularity (system/service/module/sub-module) comes from
    ``context.yaml``, not from this enum.
    """

    FEATURE = "feature"
    COMPONENT = "component"


# ---------------------------------------------------------------------------
# Header patterns per SpecKind — used by S01 to find the purpose section
# ---------------------------------------------------------------------------

_HEADER_PATTERNS: dict[SpecKind, re.Pattern[str]] = {
    SpecKind.FEATURE: re.compile(
        r"##\s*Intent\b(.*?)(?=\n##\s|\Z)",
        re.DOTALL | re.IGNORECASE,
    ),
    SpecKind.COMPONENT: re.compile(
        r"##\s*1\.?\s*Purpose\b(.*?)(?=\n##\s|\Z)",
        re.DOTALL | re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# Preset definitions — keyed by (rule_id, SpecKind)
# Returns constructor-kwarg overrides for each rule.
# Component values are empty (use code defaults).  None kind = empty.
# ---------------------------------------------------------------------------

_PRESETS: dict[tuple[str, SpecKind], dict[str, object]] = {
    # S01: One-Sentence Test
    ("S01", SpecKind.FEATURE): {
        "kind": SpecKind.FEATURE,
        "warn_conjunctions": 2,
        "fail_conjunctions": 4,
        "header_pattern": _HEADER_PATTERNS[SpecKind.FEATURE],
    },
    # S03: Stranger Test — switches to abstraction-leak mode
    ("S03", SpecKind.FEATURE): {
        "mode": "abstraction_leak",
    },
    # S04: Dependency Direction — skipped for Feature Specs
    ("S04", SpecKind.FEATURE): {
        "skip": True,
    },
    # S05: Day Test — higher thresholds for Feature Specs
    ("S05", SpecKind.FEATURE): {
        "warn_threshold": 60,
        "fail_threshold": 100,
    },
    # S08: Ambiguity Test — slightly more tolerance
    ("S08", SpecKind.FEATURE): {
        "warn_threshold": 2,
        "fail_threshold": 5,
    },
}


def get_presets(rule_id: str, kind: SpecKind | None) -> dict[str, object]:
    """Return kind-specific constructor kwargs for a rule.

    Args:
        rule_id: Rule identifier (e.g. ``"S01"``).
        kind: The spec kind.  ``None`` means "use code defaults".

    Returns:
        Dict of constructor kwargs to apply, or empty dict if no overrides.
    """
    if kind is None:
        return {}
    return dict(_PRESETS.get((rule_id, kind), {}))
