# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for all 5 language-specific StackTraceFilter implementations.

Proves: TECH-079 FR-14
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------


class TestPythonStackTraceFilter:
    def _get_filter(self) -> object:
        from specweaver.sandbox.language.core.python.stack_trace_filter import (
            PythonStackTraceFilter,
        )

        return PythonStackTraceFilter()

    def test_is_scenario_frame_true(self) -> None:
        f = self._get_filter()
        line = (
            '  File "scenarios/generated/test_payment_scenarios.py", line 42, in test_charge_happy'
        )
        assert f.is_scenario_frame(line) is True

    def test_is_scenario_frame_false_for_src(self) -> None:
        f = self._get_filter()
        line = '  File "src/payment/service.py", line 10, in charge'
        assert f.is_scenario_frame(line) is False

    def test_filter_removes_scenario_lines(self) -> None:
        f = self._get_filter()
        trace = (
            "Traceback (most recent call last):\n"
            '  File "scenarios/generated/test_payment_scenarios.py", line 42, in test_charge_happy\n'
            "    result = charge(100.0)\n"
            '  File "src/payment/service.py", line 10, in charge\n'
            "    raise ValueError\n"
            "ValueError: invalid amount\n"
        )
        result = f.filter(trace)
        assert "scenarios/generated" not in result
        assert "src/payment/service.py" in result
        assert "ValueError: invalid amount" in result

    def test_filter_empty_trace(self) -> None:
        f = self._get_filter()
        assert f.filter("") == ""

    def test_filter_no_scenario_frames(self) -> None:
        f = self._get_filter()
        trace = '  File "src/foo.py", line 1, in bar\n'
        assert f.filter(trace) == trace


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------


class TestJavaStackTraceFilter:
    def _get_filter(self) -> object:
        from specweaver.sandbox.language.core.jvm.stack_trace_filter import JvmStackTraceFilter

        return JvmStackTraceFilter()

    def test_is_scenario_frame_true(self) -> None:
        f = self._get_filter()
        line = "\tat scenarios.generated.PaymentScenariosTest.testChargeScenarios(PaymentScenariosTest.java:42)"
        assert f.is_scenario_frame(line) is True

    def test_is_scenario_frame_false_for_src(self) -> None:
        f = self._get_filter()
        line = "\tat com.example.PaymentService.charge(PaymentService.java:10)"
        assert f.is_scenario_frame(line) is False

    def test_filter_removes_scenario_frames(self) -> None:
        f = self._get_filter()
        trace = (
            "java.lang.AssertionError: expected:<ok> but was:<error>\n"
            "\tat scenarios.generated.PaymentScenariosTest.testChargeScenarios(PaymentScenariosTest.java:42)\n"
            "\tat com.example.PaymentService.charge(PaymentService.java:10)\n"
        )
        result = f.filter(trace)
        assert "scenarios.generated" not in result
        assert "com.example.PaymentService" in result

    def test_filter_preserves_exception_line(self) -> None:
        f = self._get_filter()
        trace = (
            "java.lang.AssertionError\n"
            "\tat scenarios.generated.PaymentScenariosTest.testCharge(Test.java:5)\n"
        )
        result = f.filter(trace)
        assert "java.lang.AssertionError" in result


# ---------------------------------------------------------------------------
# Kotlin
# ---------------------------------------------------------------------------


class TestKotlinStackTraceFilter:
    def _get_filter(self) -> object:
        from specweaver.sandbox.language.core.jvm.stack_trace_filter import JvmStackTraceFilter

        return JvmStackTraceFilter()

    def test_is_scenario_frame_true(self) -> None:
        f = self._get_filter()
        line = "\tat scenarios.generated.PaymentScenariosTest.testChargeScenarios(PaymentScenariosTest.kt:42)"
        assert f.is_scenario_frame(line) is True

    def test_is_scenario_frame_false(self) -> None:
        f = self._get_filter()
        line = "\tat com.example.PaymentServiceKt.charge(PaymentService.kt:10)"
        assert f.is_scenario_frame(line) is False

    def test_filter_removes_scenario_frames(self) -> None:
        f = self._get_filter()
        trace = (
            "org.opentest4j.AssertionFailedError\n"
            "\tat scenarios.generated.PaymentScenariosTest.testChargeScenarios(PaymentScenariosTest.kt:10)\n"
            "\tat com.example.PaymentServiceKt.charge(PaymentService.kt:5)\n"
        )
        result = f.filter(trace)
        assert "scenarios.generated" not in result
        assert "com.example.PaymentServiceKt" in result


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------


class TestTypeScriptStackTraceFilter:
    def _get_filter(self) -> object:
        from specweaver.sandbox.language.core.typescript.stack_trace_filter import (
            TypeScriptStackTraceFilter,
        )

        return TypeScriptStackTraceFilter()

    def test_is_scenario_frame_true(self) -> None:
        f = self._get_filter()
        line = "    at Object.<anonymous> (scenarios/generated/payment.scenarios.test.ts:42:5)"
        assert f.is_scenario_frame(line) is True

    def test_is_scenario_frame_false(self) -> None:
        f = self._get_filter()
        line = "    at PaymentService.charge (src/payment/service.ts:10:3)"
        assert f.is_scenario_frame(line) is False

    def test_filter_removes_scenario_frames(self) -> None:
        f = self._get_filter()
        trace = (
            "Error: expected ok to equal error\n"
            "    at Object.<anonymous> (scenarios/generated/payment.scenarios.test.ts:42:5)\n"
            "    at PaymentService.charge (src/payment/service.ts:10:3)\n"
        )
        result = f.filter(trace)
        assert "scenarios/generated" not in result
        assert "src/payment/service.ts" in result


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------


class TestRustStackTraceFilter:
    def _get_filter(self) -> object:
        from specweaver.sandbox.language.core.rust.stack_trace_filter import (
            RustStackTraceFilter,
        )

        return RustStackTraceFilter()

    def test_is_scenario_frame_true(self) -> None:
        f = self._get_filter()
        line = "   7: payment_scenarios::payment_scenarios::test_charge_happy"
        assert f.is_scenario_frame(line) is True

    def test_is_scenario_frame_false(self) -> None:
        f = self._get_filter()
        line = "   5: payment::service::charge"
        assert f.is_scenario_frame(line) is False

    def test_filter_removes_scenario_frames(self) -> None:
        f = self._get_filter()
        trace = (
            "thread 'payment_scenarios::test_charge_happy' panicked at 'assertion failed: false'\n"
            "   7: payment_scenarios::payment_scenarios::test_charge_happy\n"
            "   5: payment::service::charge\n"
            "note: run with RUST_BACKTRACE=1\n"
        )
        result = f.filter(trace)
        assert "_scenarios::" not in result
        assert "payment::service::charge" in result

    def test_filter_preserves_note_line(self) -> None:
        f = self._get_filter()
        trace = "   7: payment_scenarios::test_charge_happy\nnote: run with RUST_BACKTRACE=1\n"
        result = f.filter(trace)
        assert "note: run with RUST_BACKTRACE=1" in result


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestStackTraceFilterFactory:
    """TECH-079 FR-14: the run's language picks the filter from one table; nothing detects."""

    @pytest.mark.parametrize(
        ("language", "module", "name"),
        [
            ("python", "python", "PythonStackTraceFilter"),
            ("java", "jvm", "JvmStackTraceFilter"),
            ("kotlin", "jvm", "JvmStackTraceFilter"),
            ("typescript", "typescript", "TypeScriptStackTraceFilter"),
            ("rust", "rust", "RustStackTraceFilter"),
        ],
    )
    def test_each_language_gets_its_filter(self, language: str, module: str, name: str) -> None:
        import importlib

        from specweaver.sandbox.language.core.stack_trace_filter_factory import (
            create_stack_trace_filter,
        )

        expected = getattr(
            importlib.import_module(
                f"specweaver.sandbox.language.core.{module}.stack_trace_filter"
            ),
            name,
        )
        assert type(create_stack_trace_filter(language)) is expected

    @pytest.mark.parametrize("language", ["go", "Python", "", "javascript"])
    def test_an_unknown_language_is_refused_naming_it(self, language: str) -> None:
        from specweaver.sandbox.language.core.stack_trace_filter_factory import (
            create_stack_trace_filter,
        )

        with pytest.raises(ValueError, match=f"no stack trace filter for language '{language}'"):
            create_stack_trace_filter(language)
