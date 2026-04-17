# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Python scenario converter — implements ScenarioConverterInterface for pytest.

Implements ``ScenarioConverterInterface`` for Python/pytest projects.
Output location: ``scenarios/generated/test_{stem}_scenarios.py``
(pytest is directory-agnostic; no build-tool classpath constraint applies).

Note: The conversion logic lives in
``specweaver.workflows.scenarios.scenario_converter.ScenarioConverter``
and is imported lazily inside ``convert()`` to avoid a circular import
(``scenario_converter.py`` imports ``PythonScenarioConverter`` for its alias).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.loom.commons.language.interfaces import ScenarioConverterInterface

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.workflows.scenarios.scenario_models import ScenarioSet


class PythonScenarioConverter(ScenarioConverterInterface):
    """Converts a ``ScenarioSet`` to a parametrized pytest file.

    Delegates to the existing ``ScenarioConverter`` static methods (unchanged logic).
    """

    def convert(self, scenario_set: ScenarioSet) -> str:  # type: ignore[override]
        """Return pytest file content (string)."""
        # Deferred import to break circular dependency with scenario_converter.py alias
        from specweaver.workflows.scenarios.scenario_converter import (
            ScenarioConverter,
        )

        return ScenarioConverter.convert(scenario_set)

    def output_path(self, stem: str, project_root: Path) -> Path:
        """Return ``project_root/scenarios/generated/test_{stem}_scenarios.py``."""
        return project_root / "scenarios" / "generated" / f"test_{stem}_scenarios.py"
