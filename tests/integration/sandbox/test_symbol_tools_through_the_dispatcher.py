# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The code-structure tools as a model calls them: filters, short names, and honest writes.

Proves: D-SENS-02 FR-6
Proves: D-SENS-02 FR-8

| Bucket | Case |
|---|---|
| Happy | `visibility="public"` lists the public symbols; a body edit says what it wrote |
| Boundary | a comma list of visibilities; a bare method name that only one class has |
| Degradation | a bare name two classes share is refused, naming both |
| Hostile | a body that would not parse is refused and the file is left as it was |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

_CODE = """class Greeter:
    def greet(self, name: str) -> str:
        return f"Hello, {name}"

    def _secret(self) -> int:
        return 42

    def run(self) -> None:
        pass


class Waver:
    def run(self) -> None:
        pass


def helper(x: int) -> int:
    return x * 2
"""


@pytest.fixture
def call(tmp_path: Path):  # type: ignore[no-untyped-def]
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "greet.py").write_text(_CODE, encoding="utf-8")
    boundary = WorkspaceBoundary.from_run_context(
        RunContext(project_path=tmp_path, spec_path=tmp_path / "s.md")
    )
    dispatcher = ToolDispatcher.create_standard_set(
        boundary, role="implementer", allowed_tools=["ast"]
    )

    def _call(name: str, **args: Any) -> dict[str, Any]:
        return asyncio.run(dispatcher.execute(name, {"path": "src/greet.py", **args}))

    _call.file = tmp_path / "src" / "greet.py"  # type: ignore[attr-defined]
    return _call


def test_public_lists_the_public_symbols(call) -> None:  # type: ignore[no-untyped-def]
    # Proves: D-SENS-02 FR-6
    symbols = call("list_symbols", visibility="public")["symbols"]
    assert "Greeter.greet" in symbols
    assert "helper" in symbols
    assert "Greeter._secret" not in symbols


def test_a_comma_list_of_visibilities(call) -> None:  # type: ignore[no-untyped-def]
    symbols = call("list_symbols", visibility="public, internal")["symbols"]
    assert "Greeter.greet" in symbols
    assert "Greeter._secret" in symbols


def test_a_bare_name_one_class_has_finds_it(call) -> None:  # type: ignore[no-untyped-def]
    # Proves: D-SENS-02 FR-8
    assert "Hello" in call("read_symbol", symbol_name="greet")["symbol"]


def test_a_bare_name_two_classes_share_names_both(call) -> None:  # type: ignore[no-untyped-def]
    answer = call("read_symbol_body", symbol_name="run")
    assert "Greeter.run" in answer["error"]
    assert "Waver.run" in answer["error"]


def test_a_body_edit_says_what_it_wrote(call) -> None:  # type: ignore[no-untyped-def]
    # Proves: D-SENS-02 FR-8
    body = call("read_symbol_body", symbol_name="Greeter.greet")["body"]
    answer = call(
        "replace_symbol_body", symbol_name="Greeter.greet", new_code=body.replace("Hello", "Hi")
    )

    assert "error" not in answer, answer
    assert "Greeter.greet" in str(answer)
    assert 'return f"Hi, {name}"' in call.file.read_text(encoding="utf-8")


def test_a_body_that_would_not_parse_is_refused(call) -> None:  # type: ignore[no-untyped-def]
    # Proves: D-SENS-02 FR-8
    answer = call("replace_symbol_body", symbol_name="Greeter.greet", new_code="if :\n    return")

    assert "does not parse" in answer["error"]
    assert call.file.read_text(encoding="utf-8") == _CODE
