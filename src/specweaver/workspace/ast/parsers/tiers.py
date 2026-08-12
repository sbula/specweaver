# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What kind of language a parser is parsing.

`TECH-034`. `BaseTreeSitterParser` served ten languages from C++ to SQL, so a language without a
concept answered the contract with a stub — **SQL was 11 stubs out of 18 methods**, markdown 11 of
23. The stubs were not a design; they were the price of one base for everything.

Three tiers, chosen from what the parsers actually override rather than from taxonomy:

- `ClassBasedParser` — has inheritance AND annotations. Java, Kotlin, Python, TypeScript, C++.
- `FunctionBasedParser` — free functions, no inheritance. C, Go, Rust.
- `DeclarativeParser` — named declarations with no executable bodies. Markdown, SQL.

**Rust is why the axis is "has inheritance", not "is OO".** Its attributes give it decorators
without base classes, so it takes the function tier and overrides decorators — a split along
"object-oriented" would have put it in the wrong place.

**Every tier member below is a default, never a prohibition**, and that is load-bearing for what
comes next rather than a style preference. `proto` is a declarative language *with real imports*,
so a tier that forbade `extract_imports` would be wrong the day it arrives; it overrides the
default instead. Likewise `_find_target_block` stays per-language, because `lisp` has bodies with
no brace-delimited block — a tier that assumed braces is one `lisp` could not join.
"""

from __future__ import annotations

import typing
from abc import abstractmethod

from specweaver.workspace.ast.parsers.base import BaseTreeSitterParser


class ClassBasedParser(BaseTreeSitterParser):
    """A language with classes: symbols inherit, and carry annotations.

    The tier exists to make its two concepts **required**. A class-based parser that cannot report
    a base class is a gap, not a choice — which is exactly what C++ was until `TECH-034`, and it
    was invisible because the base class never asked.
    """

    @abstractmethod
    def _extract_bases(self, target_node: typing.Any) -> list[str]:
        """The types this declaration extends or implements."""

    @abstractmethod
    def _extract_decorators(self, target_node: typing.Any) -> list[str]:
        """The annotations attached to this declaration, without their sigil."""


class FunctionBasedParser(BaseTreeSitterParser):
    """A language of free functions and plain types: no inheritance hierarchy to report."""

    def _extract_bases(self, target_node: typing.Any) -> list[str]:
        """Nothing — these languages have no inheritance. Not overridden by any member today."""
        return []

    def _extract_decorators(self, target_node: typing.Any) -> list[str]:
        """Nothing by default. Rust overrides: attributes are decorators without inheritance."""
        return []

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        """Unscoped by default. Go scopes methods by receiver, Rust by `impl` block."""
        return None


class DeclarativeParser(BaseTreeSitterParser):
    """A language that declares named things and has no executable bodies.

    The defaults here are what SQL and Markdown were each writing out by hand. They are defaults
    rather than refusals: a declarative language *can* have imports — `proto` does — and overriding
    one value is a normal thing for a subclass to do.
    """

    def _is_symbol_valid(self, *args: typing.Any, **kwargs: typing.Any) -> bool:
        """Every declaration is valid: there is no body whose shape could be wrong."""
        return True

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        """No executable body to edit. Markdown overrides — a section IS its block."""
        return None

    def _extract_bases(self, target_node: typing.Any) -> list[str]:
        return []

    def _extract_decorators(self, target_node: typing.Any) -> list[str]:
        return []

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        """Unscoped by default. Markdown overrides: headings nest."""
        return None

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        """No frameworks to detect in a schema or a document."""
        return {}

    def extract_imports(self, code: str) -> list[str]:
        """None by default — **not** a refusal. `proto` will override this; see the module docstring."""
        return []
