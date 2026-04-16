# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for language-specific contract renderers in _contract_renderers.py."""

from __future__ import annotations


class TestPythonContractRenderer:
    def test_renders_protocol_class(self) -> None:
        from specweaver.core.flow._contract_renderers import render_python_protocol

        result = render_python_protocol("Payment", ["def charge(self, amount: float) -> str"], {})
        assert "class PaymentProtocol(Protocol)" in result
        assert "def charge(self, amount: float) -> str:" in result

    def test_renders_docstrings(self) -> None:
        from specweaver.core.flow._contract_renderers import render_python_protocol

        docstrings = {"charge": "Charge the card."}
        result = render_python_protocol("Payment", ["def charge(self) -> str"], docstrings)
        assert "Charge the card." in result

    def test_renders_runtime_checkable(self) -> None:
        from specweaver.core.flow._contract_renderers import render_python_protocol

        result = render_python_protocol("Order", ["def place(self) -> None"], {})
        assert "@runtime_checkable" in result

    def test_empty_signatures(self) -> None:
        from specweaver.core.flow._contract_renderers import render_python_protocol

        result = render_python_protocol("Foo", [], {})
        assert "class FooProtocol(Protocol)" in result


class TestJavaContractRenderer:
    def test_renders_interface(self) -> None:
        from specweaver.core.flow._contract_renderers import render_java_interface

        result = render_java_interface("Payment", ["def charge(self, amount: float) -> str"], {})
        assert "interface PaymentContract" in result
        assert "package contracts;" in result

    def test_renders_method_signature(self) -> None:
        from specweaver.core.flow._contract_renderers import render_java_interface

        result = render_java_interface("Payment", ["def charge(self, amount: float) -> str"], {})
        assert "charge" in result
        # Java return type should contain String
        assert "String" in result or "Object" in result

    def test_renders_docstrings_as_javadoc(self) -> None:
        from specweaver.core.flow._contract_renderers import render_java_interface

        docstrings = {"charge": "Charge the card."}
        result = render_java_interface("Payment", ["def charge(self) -> str"], docstrings)
        assert "Charge the card." in result
        assert "/**" in result or "/*" in result

    def test_extension_is_java(self) -> None:
        from specweaver.core.flow._contract_renderers import contract_extension

        assert contract_extension("java") == "java"


class TestKotlinContractRenderer:
    def test_renders_interface(self) -> None:
        from specweaver.core.flow._contract_renderers import render_kotlin_interface

        result = render_kotlin_interface("Payment", ["def charge(self, amount: float) -> str"], {})
        assert "interface PaymentContract" in result
        assert "package contracts" in result

    def test_renders_fun_signature(self) -> None:
        from specweaver.core.flow._contract_renderers import render_kotlin_interface

        result = render_kotlin_interface("Payment", ["def charge(self, amount: float) -> str"], {})
        assert "fun charge" in result

    def test_extension_is_kt(self) -> None:
        from specweaver.core.flow._contract_renderers import contract_extension

        assert contract_extension("kotlin") == "kt"


class TestTypeScriptContractRenderer:
    def test_renders_interface(self) -> None:
        from specweaver.core.flow._contract_renderers import render_typescript_interface

        result = render_typescript_interface(
            "Payment", ["def charge(self, amount: float) -> str"], {}
        )
        assert "interface PaymentContract" in result
        assert "export" in result

    def test_renders_method_signature(self) -> None:
        from specweaver.core.flow._contract_renderers import render_typescript_interface

        result = render_typescript_interface(
            "Payment", ["def charge(self, amount: float) -> str"], {}
        )
        assert "charge" in result

    def test_extension_is_ts(self) -> None:
        from specweaver.core.flow._contract_renderers import contract_extension

        assert contract_extension("typescript") == "ts"


class TestRustContractRenderer:
    def test_renders_trait(self) -> None:
        from specweaver.core.flow._contract_renderers import render_rust_trait

        result = render_rust_trait("Payment", ["def charge(self, amount: float) -> str"], {})
        assert "trait PaymentContract" in result
        assert "pub trait" in result

    def test_renders_fn_signature(self) -> None:
        from specweaver.core.flow._contract_renderers import render_rust_trait

        result = render_rust_trait("Payment", ["def charge(self, amount: float) -> str"], {})
        assert "fn charge" in result

    def test_extension_is_rs(self) -> None:
        from specweaver.core.flow._contract_renderers import contract_extension

        assert contract_extension("rust") == "rs"


class TestRenderContractDispatch:
    def test_python_dispatch(self) -> None:
        from specweaver.core.flow._contract_renderers import render_contract

        result = render_contract("python", "Foo", ["def bar(self) -> None"], {})
        assert "class FooProtocol(Protocol)" in result

    def test_java_dispatch(self) -> None:
        from specweaver.core.flow._contract_renderers import render_contract

        result = render_contract("java", "Foo", ["def bar(self) -> None"], {})
        assert "interface FooContract" in result

    def test_kotlin_dispatch(self) -> None:
        from specweaver.core.flow._contract_renderers import render_contract

        result = render_contract("kotlin", "Foo", ["def bar(self) -> None"], {})
        assert "interface FooContract" in result

    def test_typescript_dispatch(self) -> None:
        from specweaver.core.flow._contract_renderers import render_contract

        result = render_contract("typescript", "Foo", ["def bar(self) -> None"], {})
        assert "interface FooContract" in result

    def test_rust_dispatch(self) -> None:
        from specweaver.core.flow._contract_renderers import render_contract

        result = render_contract("rust", "Foo", ["def bar(self) -> None"], {})
        assert "trait FooContract" in result

    def test_unknown_defaults_to_python(self) -> None:
        from specweaver.core.flow._contract_renderers import render_contract

        result = render_contract("unknown_lang", "Foo", ["def bar(self) -> None"], {})
        assert "class FooProtocol(Protocol)" in result

    def test_contract_extension_python_default(self) -> None:
        from specweaver.core.flow._contract_renderers import contract_extension

        assert contract_extension("python") == "py"
        assert contract_extension("unknown") == "py"
