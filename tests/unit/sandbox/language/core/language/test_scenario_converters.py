# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for all 5 language-specific ScenarioConverter implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.workflows.scenarios.scenario_models import ScenarioDefinition, ScenarioSet

if TYPE_CHECKING:
    from pathlib import Path


def _make_scenario_set(spec_path: str = "specs/payment_spec.md") -> ScenarioSet:
    """Build a minimal ScenarioSet with two scenarios for different functions."""
    return ScenarioSet(
        spec_path=spec_path,
        contract_path="contracts/payment_contract.py",
        scenarios=[
            ScenarioDefinition(
                name="charge_happy",
                description="Charges the card successfully",
                function_under_test="charge",
                req_id="FR-2",
                category="happy",
                inputs={"amount": 100.0},
                expected_behavior="Returns receipt",
                expected_output={"status": "ok"},
            ),
            ScenarioDefinition(
                name="charge_error",
                description="Rejects invalid amount",
                function_under_test="charge",
                req_id="FR-2",
                category="error",
                inputs={"amount": -1.0},
                expected_behavior="Raises ValueError",
                expected_output=None,
            ),
            ScenarioDefinition(
                name="refund_happy",
                description="Refunds successfully",
                function_under_test="refund",
                req_id="FR-3",
                category="happy",
                inputs={"transaction_id": "txn-1"},
                expected_behavior="Returns confirmation",
                expected_output={"status": "refunded"},
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------


class TestPythonScenarioConverter:
    def _get_converter(self) -> object:
        from specweaver.sandbox.language.core.python.scenario_converter import (
            PythonScenarioConverter,
        )

        return PythonScenarioConverter()

    def test_convert_returns_str(self) -> None:
        converter = self._get_converter()
        result = converter.convert(_make_scenario_set())
        assert isinstance(result, str)

    def test_convert_returns_pytest_content(self) -> None:
        converter = self._get_converter()
        result = converter.convert(_make_scenario_set())
        assert "import pytest" in result

    def test_trace_tags_present(self) -> None:
        converter = self._get_converter()
        result = converter.convert(_make_scenario_set())
        assert "@trace(FR-2)" in result
        assert "@trace(FR-3)" in result

    def test_output_path_is_in_scenarios_generated(self, tmp_path: Path) -> None:
        converter = self._get_converter()
        path = converter.output_path("payment", tmp_path)
        assert path == tmp_path / "scenarios" / "generated" / "test_payment_scenarios.py"

    def test_output_path_stem_used(self, tmp_path: Path) -> None:
        converter = self._get_converter()
        path = converter.output_path("order_service", tmp_path)
        assert "order_service" in path.name

    def test_backward_compat_alias(self) -> None:
        """Original ScenarioConverter static API must still work after SF-B2.

        The static class is the backward-compat — it is NOT reassigned to
        PythonScenarioConverter. Old callers continue using ScenarioConverter.convert().
        """
        from specweaver.sandbox.language.core.python.scenario_converter import (
            PythonScenarioConverter,
        )
        from specweaver.workflows.scenarios.scenario_converter import ScenarioConverter

        ss = _make_scenario_set()
        # Old-style static call must still work
        old_result = ScenarioConverter.convert(ss)
        # New interface-based call must produce same output
        new_result = PythonScenarioConverter().convert(ss)
        assert old_result == new_result
        assert "import pytest" in old_result


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------


class TestJavaScenarioConverter:
    def _get_converter(self) -> object:
        from specweaver.sandbox.language.core.java.scenario_converter import (
            JavaScenarioConverter,
        )

        return JavaScenarioConverter()

    def test_convert_returns_str(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert isinstance(result, str)

    def test_convert_returns_junit5_content(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "@ParameterizedTest" in result or "@Test" in result

    def test_package_declaration_present(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "package scenarios.generated;" in result

    def test_method_source_present(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "@MethodSource" in result

    def test_trace_tags_present(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "@trace(FR-2)" in result

    def test_output_path_is_in_src_test_java(self, tmp_path: Path) -> None:
        path = self._get_converter().output_path("payment", tmp_path)
        assert "src" in path.parts
        assert "test" in path.parts
        assert "java" in path.parts
        assert "scenarios" in path.parts
        assert "generated" in path.parts
        assert path.suffix == ".java"
        assert "ScenariosTest" in path.name

    def test_output_path_class_name_capitalized(self, tmp_path: Path) -> None:
        path = self._get_converter().output_path("payment_service", tmp_path)
        # Stem should be converted to PascalCase
        assert path.name[0].isupper()


# ---------------------------------------------------------------------------
# Kotlin
# ---------------------------------------------------------------------------


class TestKotlinScenarioConverter:
    def _get_converter(self) -> object:
        from specweaver.sandbox.language.core.kotlin.scenario_converter import (
            KotlinScenarioConverter,
        )

        return KotlinScenarioConverter()

    def test_convert_returns_str(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert isinstance(result, str)

    def test_convert_returns_kotlin_content(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "fun test" in result or "@ParameterizedTest" in result

    def test_package_declaration_present(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "package scenarios.generated" in result

    def test_companion_object_present(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "companion object" in result

    def test_trace_tags_present(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "@trace(FR-2)" in result

    def test_output_path_is_in_src_test_kotlin(self, tmp_path: Path) -> None:
        path = self._get_converter().output_path("payment", tmp_path)
        assert "src" in path.parts
        assert "test" in path.parts
        assert "kotlin" in path.parts
        assert "scenarios" in path.parts
        assert "generated" in path.parts
        assert path.suffix == ".kt"
        assert "ScenariosTest" in path.name


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------


class TestTypeScriptScenarioConverter:
    def _get_converter(self) -> object:
        from specweaver.sandbox.language.core.typescript.scenario_converter import (
            TypeScriptScenarioConverter,
        )

        return TypeScriptScenarioConverter()

    def test_convert_returns_str(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert isinstance(result, str)

    def test_convert_returns_jest_content(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "test.each" in result or "describe" in result

    def test_test_each_present(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "test.each" in result

    def test_trace_tags_present(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "@trace(FR-2)" in result

    def test_output_path_is_in_scenarios_generated(self, tmp_path: Path) -> None:
        path = self._get_converter().output_path("payment", tmp_path)
        assert path == tmp_path / "scenarios" / "generated" / "payment.scenarios.test.ts"

    def test_output_path_correct_extension(self, tmp_path: Path) -> None:
        path = self._get_converter().output_path("order", tmp_path)
        assert path.name.endswith(".test.ts")


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------


class TestRustScenarioConverter:
    def _get_converter(self) -> object:
        from specweaver.sandbox.language.core.rust.scenario_converter import (
            RustScenarioConverter,
        )

        return RustScenarioConverter()

    def test_convert_returns_str(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert isinstance(result, str)

    def test_convert_returns_rust_content(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "#[test]" in result

    def test_cfg_test_present(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "#[cfg(test)]" in result

    def test_trace_tags_present(self) -> None:
        result = self._get_converter().convert(_make_scenario_set())
        assert "@trace(FR-2)" in result

    def test_output_path_is_in_tests_dir(self, tmp_path: Path) -> None:
        path = self._get_converter().output_path("payment", tmp_path)
        assert path == tmp_path / "tests" / "payment_scenarios.rs"
        # NOT in scenarios/generated/
        assert "scenarios" not in path.parts or path.parts[-1] != "generated"

    def test_output_path_never_in_scenarios_generated(self, tmp_path: Path) -> None:
        path = self._get_converter().output_path("order", tmp_path)
        assert "generated" not in path.parts

    def test_one_test_per_scenario(self) -> None:
        """Rust has no native parametrize — one #[test] per scenario."""
        result = self._get_converter().convert(_make_scenario_set())
        # 3 scenarios = at least 3 #[test] occurrences
        assert result.count("#[test]") >= 3


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestScenarioConverterFactory:
    def test_factory_returns_python_by_default(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.python.scenario_converter import (
            PythonScenarioConverter,
        )
        from specweaver.sandbox.language.core.scenario_converter_factory import (
            create_scenario_converter,
        )

        converter = create_scenario_converter(tmp_path)
        assert isinstance(converter, PythonScenarioConverter)

    def test_factory_returns_java_for_pom_xml(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.java.scenario_converter import (
            JavaScenarioConverter,
        )
        from specweaver.sandbox.language.core.scenario_converter_factory import (
            create_scenario_converter,
        )

        (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
        assert isinstance(create_scenario_converter(tmp_path), JavaScenarioConverter)

    def test_factory_returns_kotlin_for_build_gradle(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.kotlin.scenario_converter import (
            KotlinScenarioConverter,
        )
        from specweaver.sandbox.language.core.scenario_converter_factory import (
            create_scenario_converter,
        )

        (tmp_path / "build.gradle").write_text("plugins {}", encoding="utf-8")
        assert isinstance(create_scenario_converter(tmp_path), KotlinScenarioConverter)

    def test_factory_returns_typescript_for_package_json(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.scenario_converter_factory import (
            create_scenario_converter,
        )
        from specweaver.sandbox.language.core.typescript.scenario_converter import (
            TypeScriptScenarioConverter,
        )

        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        assert isinstance(create_scenario_converter(tmp_path), TypeScriptScenarioConverter)

    def test_factory_returns_rust_for_cargo_toml(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.rust.scenario_converter import (
            RustScenarioConverter,
        )
        from specweaver.sandbox.language.core.scenario_converter_factory import (
            create_scenario_converter,
        )

        (tmp_path / "Cargo.toml").write_text("[package]", encoding="utf-8")
        assert isinstance(create_scenario_converter(tmp_path), RustScenarioConverter)
