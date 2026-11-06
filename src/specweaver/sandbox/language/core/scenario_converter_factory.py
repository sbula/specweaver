# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which ``ScenarioConverterInterface`` a run's language gets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.sandbox.language.core.language_table import language_class

if TYPE_CHECKING:
    from specweaver.workspace.ast.parsers.interfaces import ScenarioConverterInterface

__all__ = ["create_scenario_converter"]

#: Each language's converter, as `module:class` under `sandbox.language.core`; imported on use.
_CONVERTERS = {
    "python": "python.scenario_converter:PythonScenarioConverter",
    "java": "java.scenario_converter:JavaScenarioConverter",
    "kotlin": "kotlin.scenario_converter:KotlinScenarioConverter",
    "typescript": "typescript.scenario_converter:TypeScriptScenarioConverter",
    "rust": "rust.scenario_converter:RustScenarioConverter",
}


def create_scenario_converter(language: str) -> ScenarioConverterInterface:
    """The converter for the run's language; raises `ValueError` naming an unknown one."""
    converter: ScenarioConverterInterface = language_class(
        _CONVERTERS, language, "scenario converter"
    )()
    return converter
