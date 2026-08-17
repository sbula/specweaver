# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Rule registry entry point — the registry, with every built-in rule already registered.

Usage:
    from specweaver.assurance.validation.registry import get_registry

    reg = get_registry()
    reg.register("S01", OneSentenceRule, "spec")
    cls = reg.get("S01")   # -> OneSentenceRule

Architecture:
    - The registry type and singleton live in `rule_registry`, which imports nothing.
    - This module adds the one thing that cannot live there: importing the built-in rule modules
      so they self-register. The two are separate because a module that both defines the registry
      and imports its clients is a cycle by construction.
    - Phase B: custom rules register via loader.
"""

from __future__ import annotations

# Importing these IS the registration — each module calls `get_registry().register(...)` at import
# time. Ordered after the re-export below only by convention; neither imports this module.
import specweaver.assurance.validation.rules.code.register
import specweaver.assurance.validation.rules.spec.register  # noqa: F401
from specweaver.assurance.validation.rule_registry import (
    RuleRegistry as RuleRegistry,
)
from specweaver.assurance.validation.rule_registry import (
    get_registry as get_registry,
)
