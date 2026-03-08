# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""S02: Single Test Setup — detects specs requiring multiple test environments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

# Environment categories and their keyword signals
ENV_CATEGORIES: dict[str, list[str]] = {
    "fixture": ["fixture", "sample", "example input", "test data", "mock data"],
    "runtime": ["execute", "start the engine", "invoke", "dispatch", "process request"],
    "crash_sim": ["kill", "crash", "recover", "resume", "restart", "interrupt", "sigkill"],
    "network": ["mock server", "api call", "endpoint", "http", "grpc", "webhook", "rest api"],
    "database": ["database", "sql", "sqlite", "migration", "schema", "table", "query"],
    "filesystem": [
        "file",
        "directory",
        "write to",
        "read from",
        "create directory",
        "path traversal",
    ],
    "concurrency": ["parallel", "thread", "mutex", "lock", "race", "fan-out", "semaphore"],
}


class SingleSetupRule(Rule):
    """Detect specs that need multiple distinct test environments."""

    @property
    def rule_id(self) -> str:
        return "S02"

    @property
    def name(self) -> str:
        return "Single Test Setup"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        spec_lower = spec_text.lower()
        active: list[str] = []

        for category, keywords in ENV_CATEGORIES.items():
            if any(kw in spec_lower for kw in keywords):
                active.append(category)

        findings = [
            Finding(
                message=f"Test environment category detected: {cat}",
                severity=Severity.WARNING if len(active) <= 3 else Severity.ERROR,
            )
            for cat in active
        ]

        if len(active) > 3:
            return self._fail(
                f"Requires {len(active)} test environments: {', '.join(active)} (max: 3)",
                findings,
            )

        if len(active) > 2:
            return self._warn(
                f"Borderline: {len(active)} test environments: {', '.join(active)}",
                findings,
            )

        return self._pass(f"Test environments: {len(active)} ({', '.join(active) or 'none'})")
