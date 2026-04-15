# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Factory that creates the correct ``ScenarioConverterInterface`` for a project.

Language is auto-detected by sniffing manifest files in the project root.
Re-exports ``detect_scenario_extension`` for SF-C's ``ValidateTestsHandler``
template substitution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.loom.commons.language._detect import (
    detect_language,
    detect_scenario_extension,
)

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.loom.commons.language.interfaces import ScenarioConverterInterface

# Re-export so SF-C can import from a single location
__all__ = ["create_scenario_converter", "detect_scenario_extension"]


def create_scenario_converter(cwd: Path) -> ScenarioConverterInterface:
    """Create the appropriate ``ScenarioConverterInterface`` for the detected language.

    Args:
        cwd: Project root directory to inspect for language manifest files.

    Returns:
        A concrete ``ScenarioConverterInterface`` for the detected language.
    """
    language = detect_language(cwd)

    if language == "java":
        from specweaver.core.loom.commons.language.java.scenario_converter import (
            JavaScenarioConverter,
        )
        return JavaScenarioConverter()

    if language == "kotlin":
        from specweaver.core.loom.commons.language.kotlin.scenario_converter import (
            KotlinScenarioConverter,
        )
        return KotlinScenarioConverter()

    if language == "typescript":
        from specweaver.core.loom.commons.language.typescript.scenario_converter import (
            TypeScriptScenarioConverter,
        )
        return TypeScriptScenarioConverter()

    if language == "rust":
        from specweaver.core.loom.commons.language.rust.scenario_converter import (
            RustScenarioConverter,
        )
        return RustScenarioConverter()

    # Default: Python
    from specweaver.core.loom.commons.language.python.scenario_converter import (
        PythonScenarioConverter,
    )
    return PythonScenarioConverter()
