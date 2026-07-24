# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-24 SF-03 G-d: every language converter accepts the additive `stem`
kwarg (`ScenarioConverterInterface.convert`) — the python converter consumes it
for the real-body loader anchor; the others accept-and-ignore for parity."""

from __future__ import annotations

import pytest

from specweaver.workflows.scenarios.scenario_models import ScenarioDefinition, ScenarioSet


def _scenario_set() -> ScenarioSet:
    return ScenarioSet(
        spec_path="specs/auth_spec.md",
        contract_path="contracts/auth_contract.py",
        scenarios=[
            ScenarioDefinition(
                name="happy",
                description="d",
                function_under_test="login",
                req_id="FR-1",
                inputs={"u": "a"},
                expected_output={"ok": True},
            )
        ],
    )


@pytest.mark.parametrize(
    "module_path,cls_name",
    [
        ("specweaver.sandbox.language.core.python.scenario_converter", "PythonScenarioConverter"),
        (
            "specweaver.sandbox.language.core.typescript.scenario_converter",
            "TypeScriptScenarioConverter",
        ),
        ("specweaver.sandbox.language.core.java.scenario_converter", "JavaScenarioConverter"),
        ("specweaver.sandbox.language.core.kotlin.scenario_converter", "KotlinScenarioConverter"),
        ("specweaver.sandbox.language.core.rust.scenario_converter", "RustScenarioConverter"),
    ],
)
def test_convert_accepts_stem_kwarg(module_path: str, cls_name: str) -> None:
    import importlib

    module = importlib.import_module(module_path)
    converter = getattr(module, cls_name)()
    result = converter.convert(_scenario_set(), stem="auth")
    assert isinstance(result, str)
    assert result
