# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Kotlin scenario converter — JUnit 5 Kotlin parametrized test generation.

Implements ``ScenarioConverterInterface`` for Kotlin/Gradle projects.
Output location: ``src/test/kotlin/scenarios/generated/{Stem}ScenariosTest.kt``

Why ``src/test/kotlin/``: Gradle's ``sourceSets.test.kotlin.srcDirs`` defaults to
``src/test/kotlin/``. Files outside are not compiled into the test classpath.
The ``package scenarios.generated`` declaration matches the directory structure.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.core.loom.commons.language.interfaces import ScenarioConverterInterface

if TYPE_CHECKING:
    from specweaver.workflows.scenarios.scenario_models import ScenarioSet


def _to_pascal_case(stem: str) -> str:
    return "".join(word.title() for word in stem.split("_"))


class KotlinScenarioConverter(ScenarioConverterInterface):
    """Converts a ``ScenarioSet`` to a JUnit 5 Kotlin parametrized test file."""

    def convert(self, scenario_set: ScenarioSet) -> str:  # type: ignore[override]
        stem = Path(scenario_set.spec_path).stem.replace("_spec", "")
        class_name = _to_pascal_case(stem)

        all_req_ids = sorted({s.req_id for s in scenario_set.scenarios})
        trace_tags = "\n".join(f"// @trace({r})" for r in all_req_ids)

        groups: dict[str, list[Any]] = defaultdict(list[Any])
        for s in scenario_set.scenarios:
            groups[s.function_under_test].append(s)

        method_blocks: list[Any] = []
        data_methods: list[Any] = []
        for func_name, scenarios in groups.items():
            method_blocks.append(self._render_method(func_name, scenarios))
            data_methods.append(self._render_data_method(func_name, scenarios))

        methods = "\n\n".join(method_blocks)
        companion_methods = "\n\n".join(data_methods)

        return (
            f"// Auto-generated scenario tests from spec scenarios.\n"
            f"package scenarios.generated\n"
            f"\n"
            f"{trace_tags}\n"
            f"import org.junit.jupiter.params.ParameterizedTest\n"
            f"import org.junit.jupiter.params.provider.MethodSource\n"
            f"import java.util.stream.Stream\n"
            f"import org.junit.jupiter.params.provider.Arguments\n"
            f"\n"
            f"class {class_name}ScenariosTest {{\n"
            f"\n"
            f"{methods}\n"
            f"\n"
            f"    companion object {{\n"
            f"        @JvmStatic\n"
            f"{companion_methods}\n"
            f"    }}\n"
            f"}}\n"
        )

    def _render_method(self, func_name: str, scenarios: list[Any]) -> str:
        req_ids = sorted({s.req_id for s in scenarios})
        trace_line = "    // " + " ".join(f"@trace({r})" for r in req_ids)
        method_name = "".join(w.title() for w in func_name.split("_"))
        data_method = f"{func_name}Scenarios"

        return (
            f"{trace_line}\n"
            f"    @ParameterizedTest\n"
            f"    @MethodSource(\"{data_method}\")\n"
            f"    fun test{method_name}Scenarios(scenarioName: String, expected: String) {{\n"
            f"        // TODO: implement\n"
            f"    }}"
        )

    def _render_data_method(self, func_name: str, scenarios: list[Any]) -> str:
        data_method = f"{func_name}Scenarios"
        entries = "\n".join(
            f'            Arguments.of("{s.name}", "{s.expected_behavior}"),'
            for s in scenarios
        )
        return (
            f"        @JvmStatic\n"
            f"        fun {data_method}(): Stream<Arguments> = Stream.of(\n"
            f"{entries}\n"
            f"        )"
        )

    def output_path(self, stem: str, project_root: Path) -> Path:
        """Return ``project_root/src/test/kotlin/scenarios/generated/{Stem}ScenariosTest.kt``."""
        class_name = _to_pascal_case(stem)
        return (
            project_root
            / "src" / "test" / "kotlin"
            / "scenarios" / "generated"
            / f"{class_name}ScenariosTest.kt"
        )
