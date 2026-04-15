# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Java scenario converter — JUnit 5 parametrized test generation.

Implements ``ScenarioConverterInterface`` for Java/Maven/Gradle projects.
Output location: ``src/test/java/scenarios/generated/{Stem}ScenariosTest.java``

Why ``src/test/java/``: Maven and Gradle only compile files under the declared
test source roots. Files outside are silently ignored by the build tool.
The ``package scenarios.generated;`` declaration matches the directory structure.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.core.loom.commons.language.interfaces import ScenarioConverterInterface

if TYPE_CHECKING:
    from specweaver.workflows.scenarios.scenario_models import ScenarioSet


def _to_pascal_case(stem: str) -> str:
    """Convert snake_case stem to PascalCase class name."""
    return "".join(word.title() for word in stem.split("_"))


class JavaScenarioConverter(ScenarioConverterInterface):
    """Converts a ``ScenarioSet`` to a JUnit 5 parametrized Java test file."""

    def convert(self, scenario_set: ScenarioSet) -> str:  # type: ignore[override]
        """Return JUnit 5 test class content (string)."""
        from specweaver.workflows.scenarios.scenario_models import ScenarioDefinition  # noqa: F401

        stem = Path(scenario_set.spec_path).stem.replace("_spec", "")
        class_name = _to_pascal_case(stem)

        # Collect unique req_ids across all scenarios
        all_req_ids = sorted({s.req_id for s in scenario_set.scenarios})
        trace_tags = "\n".join(f"// @trace({r})" for r in all_req_ids)

        # Group by function_under_test
        groups: dict[str, list[Any]] = defaultdict(list)
        for s in scenario_set.scenarios:
            groups[s.function_under_test].append(s)

        method_blocks: list[Any] = []
        for func_name, scenarios in groups.items():
            method_blocks.append(self._render_method(func_name, scenarios))

        methods = "\n\n".join(method_blocks)

        return (
            f"// Auto-generated scenario tests from spec scenarios.\n"
            f"package scenarios.generated;\n"
            f"\n"
            f"{trace_tags}\n"
            f"import org.junit.jupiter.params.ParameterizedTest;\n"
            f"import org.junit.jupiter.params.provider.MethodSource;\n"
            f"import java.util.stream.Stream;\n"
            f"import org.junit.jupiter.params.provider.Arguments;\n"
            f"\n"
            f"public class {class_name}ScenariosTest {{\n"
            f"\n"
            f"{methods}\n"
            f"}}\n"
        )

    def _render_method(self, func_name: str, scenarios: list[Any]) -> str:
        req_ids = sorted({s.req_id for s in scenarios})
        trace_line = "    // " + " ".join(f"@trace({r})" for r in req_ids)
        method_name = "".join(w.title() for w in func_name.split("_"))
        data_method = f"{func_name}Scenarios"

        entries = "\n".join(
            f'            Arguments.of("{s.name}", "{s.expected_behavior}"),'
            for s in scenarios
        )

        return (
            f"{trace_line}\n"
            f"    @ParameterizedTest\n"
            f"    @MethodSource(\"{data_method}\")\n"
            f"    void test{method_name}Scenarios(String scenarioName, String expected) {{\n"
            f"        // TODO: implement — scenario: \" + scenarioName + \", expected: \" + expected\n"
            f"    }}\n"
            f"\n"
            f"    static Stream<Arguments> {data_method}() {{\n"
            f"        return Stream.of(\n"
            f"{entries}\n"
            f"        );\n"
            f"    }}"
        )

    def output_path(self, stem: str, project_root: Path) -> Path:
        """Return ``project_root/src/test/java/scenarios/generated/{Stem}ScenariosTest.java``."""
        class_name = _to_pascal_case(stem)
        return (
            project_root
            / "src" / "test" / "java"
            / "scenarios" / "generated"
            / f"{class_name}ScenariosTest.java"
        )
