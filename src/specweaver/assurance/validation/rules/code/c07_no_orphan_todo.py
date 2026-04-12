# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C07: No Orphan TODO — checks for TODO/FIXME comments without ticket references."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

_TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)


class NoOrphanTodoRule(Rule):
    """Detect TODO/FIXME/HACK/XXX comments in the code."""

    @property
    def rule_id(self) -> str:
        return "C07"

    @property
    def name(self) -> str:
        return "No Orphan TODO"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        findings: list[Finding] = []

        for line_num, line in enumerate(spec_text.splitlines(), start=1):
            match = _TODO_PATTERN.search(line)
            if match:
                findings.append(
                    Finding(
                        message=f"{match.group(1).upper()} found: {line.strip()[:80]}",
                        line=line_num,
                        severity=Severity.WARNING,
                        suggestion="Resolve or remove before shipping. "
                        "Generated code should not contain TODO markers.",
                    )
                )

        if findings:
            return self._warn(f"Found {len(findings)} TODO/FIXME marker(s)", findings)

        return self._pass("No orphan TODO/FIXME markers")
