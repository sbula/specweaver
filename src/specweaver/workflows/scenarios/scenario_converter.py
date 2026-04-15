# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""ScenarioConverter — mechanical YAML scenarios to parametrized pytest.

Pure-logic transformer. No LLM involvement (NFR-2).
Produces executable pytest files with # @trace(FR-X) tags for C09 compatibility.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.workflows.scenarios.scenario_models import ScenarioDefinition, ScenarioSet


class ScenarioConverter:
    """Converts a ScenarioSet to parametrized pytest file content.

    This is a pure-logic module — no I/O, no LLM, no side effects.
    """

    @staticmethod
    def convert(scenario_set: ScenarioSet) -> str:
        """Convert a ScenarioSet to a parametrized pytest file string.

        Groups scenarios by ``function_under_test`` and generates one
        parametrized test function per group. Each test function has
        ``# @trace(FR-X)`` tags for C09 compatibility.

        Args:
            scenario_set: The scenarios to convert.

        Returns:
            A valid Python test file string.
        """
        lines: list[str] = [
            '"""Auto-generated scenario tests from spec scenarios."""',
            "",
        ]

        if not scenario_set.scenarios:
            return "\n".join(lines) + "\n"

        lines.append("import pytest")
        lines.append("")
        lines.append("")

        # Group scenarios by function_under_test
        groups: dict[str, list[ScenarioDefinition]] = defaultdict(list)
        for scenario in scenario_set.scenarios:
            groups[scenario.function_under_test].append(scenario)

        for func_name, scenarios in groups.items():
            lines.extend(
                ScenarioConverter._render_test_group(func_name, scenarios)
            )
            lines.append("")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _render_test_group(
        func_name: str,
        scenarios: list[ScenarioDefinition],
    ) -> list[str]:
        """Render a test function (possibly parametrized) for a group of scenarios."""
        lines: list[str] = []

        # Collect unique req_ids for trace tags
        req_ids = sorted({s.req_id for s in scenarios})
        for req_id in req_ids:
            lines.append(f"# @trace({req_id})")

        if len(scenarios) > 1:
            lines.extend(
                ScenarioConverter._render_parametrize_data(func_name, scenarios)
            )
        else:
            lines.extend(
                ScenarioConverter._render_single_test(func_name, scenarios[0])
            )

        return lines

    @staticmethod
    def _render_single_test(
        func_name: str,
        scenario: ScenarioDefinition,
    ) -> list[str]:
        """Render a single non-parametrized test function."""
        trace = f"  # @trace({scenario.req_id})"
        lines = [
            f"def test_{func_name}_{scenario.category}():{trace}",
            f'    """Scenario: {scenario.name} — {scenario.description}."""',
        ]
        if scenario.preconditions:
            lines.append(f"    # Preconditions: {', '.join(scenario.preconditions)}")
        lines.append(f"    # Input: {scenario.input_summary or repr(scenario.inputs)}")
        lines.append(f"    # Expected: {scenario.expected_behavior}")
        lines.append("    ...")
        return lines

    @staticmethod
    def _render_parametrize_data(
        func_name: str,
        scenarios: list[ScenarioDefinition],
    ) -> list[str]:
        """Render a @pytest.mark.parametrize test for multiple scenarios."""
        lines: list[str] = []

        # Build parametrize data
        param_entries: list[str] = []
        for s in scenarios:
            param_entries.append(
                f"    pytest.param({s.inputs!r}, {s.expected_output!r}, "
                f'id="{s.name}")'
            )

        lines.append('@pytest.mark.parametrize("inputs,expected", [')
        lines.extend(f"{entry}," for entry in param_entries)
        lines.append("])")

        # Collect req_ids for inline trace
        req_ids = sorted({s.req_id for s in scenarios})
        trace_str = "  # " + " ".join(f"@trace({rid})" for rid in req_ids)

        lines.append(f"def test_{func_name}_scenarios(inputs, expected):{trace_str}")

        # Use first scenario's description as docstring
        first = scenarios[0]
        lines.append(
            f'    """Scenario group: {func_name} — {first.description}."""'
        )
        lines.append("    ...")

        return lines

    @staticmethod
    def _render_test_function(scenario: ScenarioDefinition) -> str:
        """Render a single test function from a scenario definition.

        Args:
            scenario: Single scenario to render.

        Returns:
            String containing the test function code.
        """
        lines = ScenarioConverter._render_single_test(
            scenario.function_under_test, scenario
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Backward-compatibility note (Feature 3.28 SF-B2)
# ---------------------------------------------------------------------------
# ``ScenarioConverter`` (above) retains its original @staticmethod API.
# All existing callers continue to work unchanged.
# New code should import ``PythonScenarioConverter`` from:
#   specweaver.core.loom.commons.language.python.scenario_converter
