# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Rust test runner parsers for structural SARIF mappings."""

import logging
from typing import Any

from specweaver.commons.qa import ComplexityViolation
from specweaver.workspace.ast.parsers._sarif_complexity import parse_sarif_complexity

logger = logging.getLogger(__name__)


def parse_clippy_complexity(data: dict[str, Any], max_complexity: int) -> list[ComplexityViolation]:
    """Parse Clippy complexities strictly from structural SARIF properties without Regex."""
    logger.debug("parse_clippy_complexity called with max_complexity=%d", max_complexity)
    return parse_sarif_complexity(
        data,
        max_complexity,
        rule_markers=("cognitive_complexity", "complex"),
        drift_hint="Missing clippy property mapping?",
    )
