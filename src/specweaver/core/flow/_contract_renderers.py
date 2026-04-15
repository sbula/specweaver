# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Language-specific API contract renderers (Feature 3.28 SF-B2).

Extracted from ``_generation.py`` to keep that module within the 450-line limit
and to enable polyglot contract rendering without language branching in the handler.

Each ``render_*`` function converts extracted spec Contract signatures into the
idiomatic contract abstraction for its target language:

- Python  → ``Protocol`` class (``typing.Protocol``)
- Java    → ``interface`` with Javadoc
- Kotlin  → ``interface`` with KDoc
- TypeScript → exported ``interface``
- Rust   → ``pub trait``

Public API
----------
``render_contract(language, class_name, signatures, docstrings) -> str``
    Dispatch to the correct renderer.

``contract_extension(language) -> str``
    File extension for the generated contract (e.g. ``"py"``, ``"java"``).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Extension helpers
# ---------------------------------------------------------------------------

_EXTENSIONS: dict[str, str] = {
    "python": "py",
    "java": "java",
    "kotlin": "kt",
    "typescript": "ts",
    "rust": "rs",
}


def contract_extension(language: str) -> str:
    """Return the file extension for a generated contract file."""
    return _EXTENSIONS.get(language, "py")


# ---------------------------------------------------------------------------
# Python — typing.Protocol
# ---------------------------------------------------------------------------


def render_python_protocol(
    class_name: str,
    signatures: list[str],
    docstrings: dict[str, str] | None = None,
) -> str:
    """Render a Python Protocol class from extracted signatures and docstrings."""
    docstrings = docstrings or {}
    lines: list[str] = [
        '"""Auto-generated API contract from spec Contract section."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Protocol, runtime_checkable",
        "",
        "",
        "@runtime_checkable",
        f"class {class_name}Protocol(Protocol):",
        f'    """API contract for {class_name}."""',
        "",
    ]
    for sig in signatures:
        lines.append(f"    {sig}:")
        func_match = re.search(r"def\s+(\w+)\(", sig)
        func_name = func_match.group(1) if func_match else None
        if func_name and func_name in docstrings:
            lines.append(f'        """{docstrings[func_name]}"""')
        else:
            lines.append("        ...")
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Java — interface
# ---------------------------------------------------------------------------


def _py_sig_to_java_method(sig: str, docstring: str | None) -> str:
    """Convert a Python function signature to a Java abstract method declaration."""
    func_match = re.search(r"def\s+(\w+)\(", sig)
    func_name = func_match.group(1) if func_match else "unknown"

    # Map Python return type annotation hints to Java types (best-effort)
    return_type = "Object"
    ret_match = re.search(r"->\s*(\w+)", sig)
    if ret_match:
        py_ret = ret_match.group(1)
        _type_map = {
            "str": "String", "int": "int", "float": "double",
            "bool": "boolean", "None": "void", "list": "List",
            "dict": "Map", "Any": "Object",
        }
        return_type = _type_map.get(py_ret, "Object")

    javadoc = ""
    if docstring:
        javadoc = f"    /**\n     * {docstring}\n     */\n"
    return f"{javadoc}    {return_type} {func_name}(Object... args);"


def render_java_interface(
    class_name: str,
    signatures: list[str],
    docstrings: dict[str, str] | None = None,
) -> str:
    """Render a Java interface from extracted signatures."""
    docstrings = docstrings or {}
    methods: list[str] = []
    for sig in signatures:
        func_match = re.search(r"def\s+(\w+)\(", sig)
        func_name = func_match.group(1) if func_match else None
        doc = docstrings.get(func_name, "") if func_name else ""
        methods.append(_py_sig_to_java_method(sig, doc or None))

    method_block = "\n".join(methods)
    return (
        f"// Auto-generated API contract from spec Contract section.\n"
        f"package contracts;\n"
        f"\n"
        f"/**\n"
        f" * API contract for {class_name}.\n"
        f" */\n"
        f"public interface {class_name}Contract {{\n"
        f"\n"
        f"{method_block}\n"
        f"}}\n"
    )


# ---------------------------------------------------------------------------
# Kotlin — interface
# ---------------------------------------------------------------------------


def _py_sig_to_kotlin_fun(sig: str, docstring: str | None) -> str:
    """Convert a Python function signature to a Kotlin abstract fun declaration."""
    func_match = re.search(r"def\s+(\w+)\(", sig)
    func_name = func_match.group(1) if func_match else "unknown"

    return_type = "Any"
    ret_match = re.search(r"->\s*(\w+)", sig)
    if ret_match:
        py_ret = ret_match.group(1)
        _type_map = {
            "str": "String", "int": "Int", "float": "Double",
            "bool": "Boolean", "None": "Unit", "list": "List<Any>",
            "dict": "Map<String, Any>", "Any": "Any",
        }
        return_type = _type_map.get(py_ret, "Any")

    kdoc = ""
    if docstring:
        kdoc = f"    /**\n     * {docstring}\n     */\n"
    return f"{kdoc}    fun {func_name}(vararg args: Any): {return_type}"


def render_kotlin_interface(
    class_name: str,
    signatures: list[str],
    docstrings: dict[str, str] | None = None,
) -> str:
    """Render a Kotlin interface from extracted signatures."""
    docstrings = docstrings or {}
    methods: list[str] = []
    for sig in signatures:
        func_match = re.search(r"def\s+(\w+)\(", sig)
        func_name = func_match.group(1) if func_match else None
        doc = docstrings.get(func_name, "") if func_name else ""
        methods.append(_py_sig_to_kotlin_fun(sig, doc or None))

    method_block = "\n".join(methods)
    return (
        f"// Auto-generated API contract from spec Contract section.\n"
        f"package contracts\n"
        f"\n"
        f"/**\n"
        f" * API contract for {class_name}.\n"
        f" */\n"
        f"interface {class_name}Contract {{\n"
        f"\n"
        f"{method_block}\n"
        f"}}\n"
    )


# ---------------------------------------------------------------------------
# TypeScript — exported interface
# ---------------------------------------------------------------------------


def _py_sig_to_ts_method(sig: str, docstring: str | None) -> str:
    func_match = re.search(r"def\s+(\w+)\(", sig)
    func_name = func_match.group(1) if func_match else "unknown"

    return_type = "unknown"
    ret_match = re.search(r"->\s*(\w+)", sig)
    if ret_match:
        py_ret = ret_match.group(1)
        _type_map = {
            "str": "string", "int": "number", "float": "number",
            "bool": "boolean", "None": "void", "list": "unknown[]",
            "dict": "Record<string, unknown>", "Any": "unknown",
        }
        return_type = _type_map.get(py_ret, "unknown")

    jsdoc = ""
    if docstring:
        jsdoc = f"  /** {docstring} */\n"
    return f"{jsdoc}  {func_name}(...args: unknown[]): {return_type};"


def render_typescript_interface(
    class_name: str,
    signatures: list[str],
    docstrings: dict[str, str] | None = None,
) -> str:
    """Render an exported TypeScript interface from extracted signatures."""
    docstrings = docstrings or {}
    methods: list[str] = []
    for sig in signatures:
        func_match = re.search(r"def\s+(\w+)\(", sig)
        func_name = func_match.group(1) if func_match else None
        doc = docstrings.get(func_name, "") if func_name else ""
        methods.append(_py_sig_to_ts_method(sig, doc or None))

    method_block = "\n".join(methods)
    return (
        f"// Auto-generated API contract from spec Contract section.\n"
        f"\n"
        f"/** API contract for {class_name}. */\n"
        f"export interface {class_name}Contract {{\n"
        f"{method_block}\n"
        f"}}\n"
    )


# ---------------------------------------------------------------------------
# Rust — pub trait
# ---------------------------------------------------------------------------


def _py_sig_to_rust_fn(sig: str, docstring: str | None) -> str:
    func_match = re.search(r"def\s+(\w+)\(", sig)
    func_name = func_match.group(1) if func_match else "unknown"
    # Convert camelCase/snake_case Python name to snake_case (it usually already is)
    rust_name = re.sub(r"([A-Z])", lambda m: f"_{m.group(1).lower()}", func_name).lstrip("_")

    return_type = "()"
    ret_match = re.search(r"->\s*(\w+)", sig)
    if ret_match:
        py_ret = ret_match.group(1)
        _type_map = {
            "str": "String", "int": "i64", "float": "f64",
            "bool": "bool", "None": "()", "list": "Vec<Box<dyn std::any::Any>>",
            "dict": "std::collections::HashMap<String, Box<dyn std::any::Any>>",
            "Any": "Box<dyn std::any::Any>",
        }
        return_type = _type_map.get(py_ret, "Box<dyn std::any::Any>")

    doc_comment = ""
    if docstring:
        doc_comment = f"    /// {docstring}\n"
    return f"{doc_comment}    fn {rust_name}(&self) -> {return_type};"


def render_rust_trait(
    class_name: str,
    signatures: list[str],
    docstrings: dict[str, str] | None = None,
) -> str:
    """Render a Rust pub trait from extracted signatures."""
    docstrings = docstrings or {}
    methods: list[str] = []
    for sig in signatures:
        func_match = re.search(r"def\s+(\w+)\(", sig)
        func_name = func_match.group(1) if func_match else None
        doc = docstrings.get(func_name, "") if func_name else ""
        methods.append(_py_sig_to_rust_fn(sig, doc or None))

    method_block = "\n".join(methods)
    # PascalCase trait name
    trait_name = "".join(w.title() for w in class_name.replace("-", "_").split("_"))
    return (
        f"// Auto-generated API contract from spec Contract section.\n"
        f"\n"
        f"/// API contract for {class_name}.\n"
        f"pub trait {trait_name}Contract {{\n"
        f"{method_block}\n"
        f"}}\n"
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def render_contract(
    language: str,
    class_name: str,
    signatures: list[str],
    docstrings: dict[str, str] | None = None,
) -> str:
    """Dispatch to the appropriate renderer for the given language.

    Args:
        language: Canonical language name (e.g. ``"python"``, ``"java"``).
        class_name: Pascal-case base name for the generated class/interface.
        signatures: List of extracted function signature strings.
        docstrings: Optional mapping of function name → docstring.

    Returns:
        Complete contract file content as a string.
    """
    docstrings = docstrings or {}
    if language == "java":
        return render_java_interface(class_name, signatures, docstrings)
    if language == "kotlin":
        return render_kotlin_interface(class_name, signatures, docstrings)
    if language == "typescript":
        return render_typescript_interface(class_name, signatures, docstrings)
    if language == "rust":
        return render_rust_trait(class_name, signatures, docstrings)
    # Default — Python and any unknown
    return render_python_protocol(class_name, signatures, docstrings)
