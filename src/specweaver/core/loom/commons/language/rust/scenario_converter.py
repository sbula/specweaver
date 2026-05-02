# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Rust scenario converter — integration test generation.

Implements ``ScenarioConverterInterface`` for Rust/Cargo projects.
Output location: ``tests/{stem}_scenarios.rs``

Why ``tests/``: Rust's compiler treats files in ``tests/`` as independent
integration test crates. This is a compiler-level convention, not configurable.
Rust has no native parametrize support; one ``#[test]`` function is generated
per scenario definition.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.workspace.ast.parsers.interfaces import ScenarioConverterInterface

if TYPE_CHECKING:
    from specweaver.workflows.scenarios.scenario_models import ScenarioSet


def _to_snake_case(name: str) -> str:
    """Ensure name is safe as a Rust function identifier."""
    return name.lower().replace("-", "_").replace(" ", "_")


class RustScenarioConverter(ScenarioConverterInterface):
    """Converts a ``ScenarioSet`` to Rust integration tests (one per scenario)."""

    def convert(self, scenario_set: ScenarioSet) -> str:  # type: ignore[override]
        stem = Path(scenario_set.spec_path).stem.replace("_spec", "")
        mod_name = _to_snake_case(stem) + "_scenarios"

        all_req_ids = sorted({s.req_id for s in scenario_set.scenarios})
        trace_tags = "\n".join(f"// @trace({r})" for r in all_req_ids)

        test_fns: list[str] = []
        for s in scenario_set.scenarios:
            fn_name = f"test_{_to_snake_case(s.function_under_test)}_{_to_snake_case(s.category)}"
            # Make unique if multiple same-category scenarios exist for the same function
            if any(t.endswith(fn_name) for t in test_fns):
                fn_name = f"{fn_name}_{_to_snake_case(s.name)}"

            req_comment = f"    // @trace({s.req_id})"
            test_fns.append(
                f"    #[test]\n"
                f"    fn {fn_name}() {{\n"
                f"{req_comment}\n"
                f"        // Scenario: {s.name} — {s.description}\n"
                f"        // Input: {s.input_summary or repr(s.inputs)}\n"
                f"        // Expected: {s.expected_behavior}\n"
                f"        todo!()\n"
                f"    }}"
            )

        functions = "\n\n".join(test_fns)

        return (
            f"// Auto-generated scenario tests from spec scenarios.\n"
            f"{trace_tags}\n"
            f"\n"
            f"#[cfg(test)]\n"
            f"mod {mod_name} {{\n"
            f"\n"
            f"{functions}\n"
            f"}}\n"
        )

    def output_path(self, stem: str, project_root: Path) -> Path:
        """Return ``project_root/tests/{stem}_scenarios.rs``.

        Rust integration tests MUST live in ``tests/`` (compiler-enforced).
        """
        return project_root / "tests" / f"{stem}_scenarios.rs"
