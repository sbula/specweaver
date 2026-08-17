# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The rule registry type and its process-wide singleton.

Separating the *contract* from the *trigger* keeps the module graph acyclic: a module that both
defines the registry and imports the clients that register with it is a cycle by construction. This
module holds the contract and imports nothing, so both the rules and `registry.py` can sit above it:

    registry  ->  rules.{spec,code}.register  ->  rule_registry

`registry.py` remains the public entry point and still guarantees built-ins are loaded, so every
existing `from ...validation.registry import get_registry` keeps working unchanged. That mattered:
the auto-registration is relied on by callers that never mention the rules modules, and a fix that
made them opt in would have failed silently, with rules simply missing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from specweaver.assurance.validation.models import Rule

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
