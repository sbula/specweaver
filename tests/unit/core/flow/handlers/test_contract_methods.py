# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A contract keeps each method's owner: `greet` for a function, `Greeter.greet` for a method.

Proves: B-FLOW-01 FR-2

| Bucket | Case |
|---|---|
| Happy | a class and a function: both named, each language renders the class's own type |
| Boundary | functions only: the file is the same as before, byte for byte; `__init__` and `_private` are not methods |
| Degradation | a Java file has one public type, however many classes the spec has |
| Hostile | a `def` inside a function is not a contract method |
"""

from __future__ import annotations

import pytest

from specweaver.core.flow.handlers.contract_renderers import (
    contract_names,
    extract_docstrings,
    extract_methods,
    extract_signatures,
    render_contract,
    render_contract_file,
)

_LANGUAGES = ["python", "java", "kotlin", "typescript", "rust"]

_MIXED = '''
```python
class Greeter:
    def __init__(self, greeting: str) -> None:
        """Keep the greeting."""

    def greet(self, name: str) -> str:
        """Return the greeting and the name."""

    def _shout(self, text: str) -> str:
        """Not part of the contract."""

def farewell(name: str) -> str:
    """Return the farewell."""
```
'''

_FUNCTIONS = '''
```python
def greet(name: str) -> str:
    """Return the salutation."""

def farewell(name: str) -> str:
    """Return the farewell."""
```
'''


def test_a_method_keeps_its_class() -> None:
    assert contract_names(extract_methods(_MIXED)) == ["Greeter.greet", "farewell"]


@pytest.mark.parametrize(
    ("language", "type_line"),
    [
        ("python", "class GreeterProtocol(Protocol):"),
        ("java", "interface GreeterContract {"),
        ("kotlin", "interface GreeterContract {"),
        ("typescript", "export interface GreeterContract {"),
        ("rust", "pub trait GreeterContract {"),
    ],
)
def test_each_language_renders_the_class(language: str, type_line: str) -> None:
    text = render_contract_file(language, "Greet", extract_methods(_MIXED))

    assert type_line in text
    assert "greet" in text.split(type_line, 1)[1]
    assert "Greet" in text.replace("Greeter", "")


def test_the_python_method_keeps_self_and_its_docstring() -> None:
    text = render_contract_file("python", "Greet", extract_methods(_MIXED))

    greeter = text.split("class GreeterProtocol(Protocol):", 1)[1]
    assert "def greet(self, name: str) -> str:" in greeter
    assert "Return the greeting and the name." in greeter
    assert "_shout" not in text
    assert "__init__" not in greeter


@pytest.mark.parametrize("language", _LANGUAGES)
def test_functions_only_give_the_same_file_as_before(language: str) -> None:
    before = render_contract(
        language, "Greet", extract_signatures(_FUNCTIONS), extract_docstrings(_FUNCTIONS)
    )

    assert render_contract_file(language, "Greet", extract_methods(_FUNCTIONS)) == before


def test_a_class_with_only_a_constructor_has_no_method() -> None:
    text = "```python\nclass Box:\n    def __init__(self, size: int) -> None:\n        ...\n```\n"

    assert contract_names(extract_methods(text)) == []


def test_a_java_file_has_one_public_type() -> None:
    text = render_contract_file("java", "Greet", extract_methods(_MIXED))

    assert text.count("public interface") == 1
    assert text.count("package contracts;") == 1


def test_a_def_inside_a_function_is_not_a_method() -> None:
    text = (
        "```python\ndef outer(x: int) -> int:\n    def inner(y: int) -> int:\n"
        "        return y\n    return inner(x)\n```\n"
    )

    assert contract_names(extract_methods(text)) == ["outer"]


def test_no_methods_give_an_empty_type() -> None:
    assert render_contract_file("python", "Greet", []) == render_contract("python", "Greet", [], {})


def test_the_first_method_under_a_class_counts() -> None:
    text = "```python\nclass Box:\n    def open(self) -> None:\n        ...\n```\n"

    assert contract_names(extract_methods(text)) == ["Box.open"]
