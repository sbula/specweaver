# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TypeScript scenario converter — Jest parametrized test generation.

Implements ``ScenarioConverterInterface`` for TypeScript/Jest projects.
Output location: ``scenarios/generated/{stem}.scenarios.test.ts``

Jest's default ``testMatch: ["**/*.test.ts"]`` covers ``scenarios/generated/``
as long as ``rootDir`` is the project root (the Jest default). No config changes needed.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.workspace.ast.parsers.interfaces import ScenarioConverterInterface

if TYPE_CHECKING:
    from specweaver.workflows.scenarios.scenario_models import ScenarioSet


class TypeScriptScenarioConverter(ScenarioConverterInterface):
    """Converts a ``ScenarioSet`` to a Jest ``test.each`` test file."""

    def convert(self, scenario_set: ScenarioSet) -> str:  # type: ignore[override]
        Path(scenario_set.spec_path).stem.replace("_spec", "")

        all_req_ids = sorted({s.req_id for s in scenario_set.scenarios})
        trace_tags = "\n".join(f"// @trace({r})" for r in all_req_ids)

        groups: dict[str, list[Any]] = defaultdict(list)
        for s in scenario_set.scenarios:
            groups[s.function_under_test].append(s)

        describe_blocks: list[Any] = []
        for func_name, scenarios in groups.items():
            describe_blocks.append(self._render_describe(func_name, scenarios))

        describes = "\n\n".join(describe_blocks)

        return (
            f"// Auto-generated scenario tests from spec scenarios.\n{trace_tags}\n\n{describes}\n"
        )

    def _render_describe(self, func_name: str, scenarios: list[Any]) -> str:
        req_ids = sorted({s.req_id for s in scenarios})
        trace_comment = "  // " + " ".join(f"@trace({r})" for r in req_ids)

        rows = "\n".join(
            f"    {{ scenarioName: '{s.name}', expected: '{s.expected_behavior}' }},"
            for s in scenarios
        )

        return (
            f"describe('{func_name} scenarios', () => {{\n"
            f"{trace_comment}\n"
            f"  test.each([\n"
            f"{rows}\n"
            f"  ])('$scenarioName', ({{ scenarioName, expected }}) => {{\n"
            f'    // TODO: implement — expected: " + expected\n'
            f"    expect(true).toBe(true);\n"
            f"  }});\n"
            f"}});"
        )

    def output_path(self, stem: str, project_root: Path) -> Path:
        """Return ``project_root/scenarios/generated/{stem}.scenarios.test.ts``."""
        return project_root / "scenarios" / "generated" / f"{stem}.scenarios.test.ts"
