# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Rule registry -- maps rule IDs to Rule classes.

Central registry for all validation rules (built-in and custom).
The runner queries the registry instead of using hardcoded imports.

Usage:
    from specweaver.validation.registry import get_registry

    reg = get_registry()
    reg.register("S01", OneSentenceRule, "spec")
    cls = reg.get("S01")   # -> OneSentenceRule

Architecture:
    - Lives in validation/ (not loom/) per context.yaml constraints.
    - Module-level singleton via get_registry().
    - Phase A: built-in rules auto-register on import.
    - Phase B: custom rules register via loader.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from specweaver.validation.models import Rule

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = frozenset({"spec", "code"})


class RuleRegistry:
    """Maps rule_id to Rule class + category.

    Thread-safe enough for single-threaded SpecWeaver usage.
    """

    def __init__(self) -> None:
        self._rules: dict[str, tuple[type[Rule], str]] = {}

    def register(
        self,
        rule_id: str,
        rule_class: type[Rule],
        category: Literal["spec", "code"],
    ) -> None:
        """Register a rule class.

        Args:
            rule_id: Unique identifier (e.g. 'S01', 'C04', 'D01').
            rule_class: The Rule subclass (not an instance).
            category: Either 'spec' or 'code'.

        Raises:
            ValueError: If rule_id is already registered or category is invalid.
        """
        if category not in _VALID_CATEGORIES:
            msg = (
                f"Invalid category '{category}' for rule '{rule_id}'. "
                f"Must be one of: {sorted(_VALID_CATEGORIES)}"
            )
            logger.warning("register: invalid category '%s' for rule '%s'", category, rule_id)
            raise ValueError(msg)

        if rule_id in self._rules:
            existing_cls = self._rules[rule_id][0]
            msg = (
                f"Rule '{rule_id}' already registered "
                f"({existing_cls.__name__}). Cannot re-register "
                f"with {rule_class.__name__}."
            )
            logger.warning(
                "register: rule '%s' already registered as %s", rule_id, existing_cls.__name__
            )
            raise ValueError(msg)

        self._rules[rule_id] = (rule_class, category)
        logger.debug("Registered rule %s (%s, category=%s)", rule_id, rule_class.__name__, category)

    def get(self, rule_id: str) -> type[Rule] | None:
        """Get a rule class by ID, or None if not registered."""
        entry = self._rules.get(rule_id)
        return entry[0] if entry else None

    def list_spec(self) -> list[tuple[str, type[Rule]]]:
        """All registered spec rules, sorted by rule_id."""
        return sorted(
            [(rid, cls) for rid, (cls, cat) in self._rules.items() if cat == "spec"],
            key=lambda x: x[0],
        )

    def list_code(self) -> list[tuple[str, type[Rule]]]:
        """All registered code rules, sorted by rule_id."""
        return sorted(
            [(rid, cls) for rid, (cls, cat) in self._rules.items() if cat == "code"],
            key=lambda x: x[0],
        )

    def list_all(self) -> list[tuple[str, type[Rule], str]]:
        """All rules: (rule_id, rule_class, category), sorted by rule_id."""
        return sorted(
            [(rid, cls, cat) for rid, (cls, cat) in self._rules.items()],
            key=lambda x: x[0],
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry = RuleRegistry()


def get_registry() -> RuleRegistry:
    """Get the global rule registry."""
    return _registry


# Auto-register standard rules upon import
import specweaver.validation.rules.code.register  # noqa: E402
import specweaver.validation.rules.spec.register  # noqa: F401, E402
