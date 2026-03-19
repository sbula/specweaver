# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Domain profiles — named preset bundles for validation threshold calibration.

Each profile maps rule IDs to RuleOverride values.  Applying a profile
bulk-writes these overrides to the project's DB, replacing any existing
overrides.

Usage::

    from specweaver.config.profiles import get_profile, list_profiles

    profile = get_profile("web-app")
    if profile:
        for rule_id, override in profile.overrides.items():
            db.set_validation_override(project, rule_id, ...)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from specweaver.config.settings import RuleOverride

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainProfile:
    """A named collection of validation overrides for a project domain.

    Attributes:
        name: Profile identifier (e.g. ``"web-app"``).
        description: Human-readable description of the profile.
        overrides: Mapping of rule_id → RuleOverride values.
    """

    name: str
    description: str
    overrides: dict[str, RuleOverride] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

PROFILES: dict[str, DomainProfile] = {
    "web-app": DomainProfile(
        name="web-app",
        description="Balanced thresholds for web applications",
        overrides={
            "S03": RuleOverride(rule_id="S03", warn_threshold=3, fail_threshold=5),
            "S05": RuleOverride(rule_id="S05", warn_threshold=30, fail_threshold=50),
            "S08": RuleOverride(rule_id="S08", warn_threshold=3, fail_threshold=8),
            "C04": RuleOverride(rule_id="C04", fail_threshold=70),
        },
    ),
    "data-pipeline": DomainProfile(
        name="data-pipeline",
        description="Lenient on complexity and external references for ETL/batch pipelines",
        overrides={
            "S03": RuleOverride(rule_id="S03", warn_threshold=6, fail_threshold=10),
            "S05": RuleOverride(rule_id="S05", warn_threshold=50, fail_threshold=80),
            "S08": RuleOverride(rule_id="S08", warn_threshold=5, fail_threshold=12),
            "C04": RuleOverride(rule_id="C04", fail_threshold=60),
        },
    ),
    "library": DomainProfile(
        name="library",
        description="Strict thresholds for public-facing libraries and SDKs",
        overrides={
            "S03": RuleOverride(rule_id="S03", warn_threshold=2, fail_threshold=4),
            "S05": RuleOverride(rule_id="S05", warn_threshold=20, fail_threshold=40),
            "S07": RuleOverride(rule_id="S07", warn_threshold=8, fail_threshold=6),
            "S08": RuleOverride(rule_id="S08", warn_threshold=2, fail_threshold=5),
            "S11": RuleOverride(rule_id="S11", warn_threshold=2, fail_threshold=4),
            "C04": RuleOverride(rule_id="C04", fail_threshold=85),
        },
    ),
    "microservice": DomainProfile(
        name="microservice",
        description="Tuned for service boundaries and contract clarity",
        overrides={
            "S03": RuleOverride(rule_id="S03", warn_threshold=3, fail_threshold=5),
            "S05": RuleOverride(rule_id="S05", warn_threshold=25, fail_threshold=45),
            "S08": RuleOverride(rule_id="S08", warn_threshold=3, fail_threshold=8),
            "C04": RuleOverride(rule_id="C04", fail_threshold=75),
        },
    ),
    "ml-model": DomainProfile(
        name="ml-model",
        description="Very lenient thresholds for ML/AI projects with research-style specs",
        overrides={
            "S03": RuleOverride(rule_id="S03", warn_threshold=8, fail_threshold=12),
            "S05": RuleOverride(rule_id="S05", warn_threshold=80, fail_threshold=120),
            "S07": RuleOverride(rule_id="S07", warn_threshold=4, fail_threshold=3),
            "S08": RuleOverride(rule_id="S08", warn_threshold=8, fail_threshold=15),
            "S11": RuleOverride(rule_id="S11", warn_threshold=5, fail_threshold=8),
            "C04": RuleOverride(rule_id="C04", fail_threshold=50),
        },
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_profile(name: str) -> DomainProfile | None:
    """Get a profile by name (case-insensitive).

    Args:
        name: Profile name (e.g. ``"web-app"`` or ``"WEB-APP"``).

    Returns:
        The matching ``DomainProfile``, or ``None`` if not found.
    """
    if not name:
        return None
    return PROFILES.get(name.lower())


def list_profiles() -> list[DomainProfile]:
    """Return all available profiles, sorted by name.

    Returns:
        List of ``DomainProfile`` instances in alphabetical order.
    """
    return sorted(PROFILES.values(), key=lambda p: p.name)
