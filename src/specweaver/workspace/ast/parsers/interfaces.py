# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Interfaces for AST-based code parsing and skeleton extraction."""

from __future__ import annotations

import logging
import typing
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from pathlib import Path


class CodeStructureError(Exception):
    """Raised when the CodeStructure parser encounters a fatal error or cannot resolve a symbol."""


#: The one vocabulary every language's access levels normalise onto.
#:
#: Ten languages disagree, and a consumer filtering across them cannot work on raw keywords: Java
#: says `package-private`, Kotlin `internal`, Rust `pub(crate)`, Go says nothing at all and encodes
#: it in capitalisation. They are the same idea -- *visible inside this module, not outside it* --
#: so they are one word here.
#:
#: **`internal` is not a softer `private`.** Go has no `private`: a lowercase identifier is visible
#: to its whole package, and mapping it to `private` would hide code from the package-mates
#: entitled to use it. The distinction is the reason this is five words and not three.
#:
#: **`unknown` means the language cannot say**, as SQL and markdown cannot. Recorded as its own
#: word rather than as `public`, so nothing downstream ever reads a claim the language never made.
VISIBILITY: tuple[str, ...] = ("public", "protected", "internal", "private", "unknown")

#: The same set as a type, so mypy rejects a typo that the tuple alone would only catch at runtime.
Visibility = typing.Literal["public", "protected", "internal", "private", "unknown"]


class CodeStructureInterface(ABC):
    """Common abstraction for Polyglot AST extraction.

    This layer receives raw code strings from atoms and performs pure logic
    Tree-Sitter .scm queries to safely extract interface skeletons or symbol bodies.
    IO-bound operations are blocked from entering this component.
    """

    parser: typing.Any

    @abstractmethod
    def extract_skeleton(self, code: str) -> str:
        """Extract a simplified structural "skeleton" of the source code.

        The skeleton must contain ONLY:
        - Class definitions (with docstrings)
        - Method/Function signatures (with docstrings)
        - Imports

        All internal implementation bodies must be omitted.

        Args:
            code: The raw source code of the file.

        Returns:
            The raw string containing ONLY the file's interfaces.
        """

    @abstractmethod
    def extract_symbol(self, code: str, symbol_name: str) -> str:
        """Extract the exact full source code string of a specific symbol.

        Args:
            code: The raw source code of the file.
            symbol_name: The target node (e.g., 'MyClass' or 'my_function').

        Returns:
            The raw implementation string of the requested symbol.

        Raises:
            CodeStructureError: If the symbol cannot be found in the AST.
        """

    @abstractmethod
    def extract_symbol_body(self, code: str, symbol_name: str) -> str:
        """Extract the exact full source code string of a specific symbol's internal body block.

        This prevents mutation of the symbol's decorators or signature when performing rewrites.

        Args:
            code: The raw source code of the file.
            symbol_name: The target node (e.g., 'MyClass' or 'my_function').

        Returns:
            The raw execution logic inside the symbol bounds (e.g. `{...}` or `...`).

        Raises:
            CodeStructureError: If the symbol cannot be found in the AST.
        """

    @abstractmethod
    def extract_symbol_doc(self, code: str, symbol_name: str) -> str:
        """The description attached to one symbol, with its comment markers removed.

        `""` when the symbol has none, when the language has no doc-comment concept, or when the
        nearest comment is separated from the declaration by a blank line — a note about something
        else rather than a description of this.

        **Never raises**, for the same reason `extract_symbol_visibility` does not: it is called
        once per symbol during a whole-repository scan.
        """

    @abstractmethod
    def extract_symbol_visibility(self, code: str, symbol_name: str) -> Visibility:
        """The access level of one symbol, as a word from `VISIBILITY`.

        Answers *what* a symbol's visibility is, where `list_symbols(visibility=...)` only ever
        answered *does it match*. A consumer that has to label a symbol -- rather than filter a
        list -- has no other way to ask.

        **Never raises.** This is called once per symbol during a whole-repository scan, so a name
        that cannot be found, an empty file or source no grammar can read all answer `unknown`
        rather than taking the scan down with them.

        Args:
            code: The raw source code of the file.
            symbol_name: A name as `list_symbols` reports it, dot-scoped (e.g. `Order.submit`).

        Returns:
            One of `VISIBILITY`.
        """

    @abstractmethod
    def list_symbols(
        self, code: str, visibility: list[str] | None = None, decorator_filter: str | None = None
    ) -> list[str]:
        """Dynamically map and list all targetable symbols within a file.

        Args:
            code: The raw source code of the file.
            visibility: Optional list to limit the payload to explicit access boundaries (e.g. ['public']).
            decorator_filter: Optional filter to return exclusively symbols holding specific markers.

        Returns:
            A flat array of all targetable symbols.
        """

    @abstractmethod
    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        """Extract framework-specific markers like annotations, decorators, and inheritance."""

    @abstractmethod
    def extract_supertypes(self, code: str) -> dict[str, dict[str, list[str]]]:
        """Each type's supertypes, with extension and implementation kept apart.

        Returns:
            `{type_name: {"extends": [...], "implements": [...]}}`. A language whose grammar does
            not separate the two reports everything under `extends` rather than guessing — Kotlin
            holds both in one `delegation_specifiers` list where only a parenthesis convention
            distinguishes them, and `by` delegation breaks that convention.

        Separate from `extract_framework_markers`, whose flat `extends` list has callers outside the
        graph and must not change shape.
        """

    @abstractmethod
    def extract_call_sites(self, code: str) -> dict[str, list[str]]:
        """Each symbol mapped to the bare names it calls.

        Returns:
            `{qualified_caller: [callee, ...]}`. A call outside any declaration is attributed to the
            empty key, meaning the file itself — module-level code is a real dependency. A language
            whose grammar ships no call query reports nothing rather than raising.
        """

    @abstractmethod
    def extract_traceability_tags(self, code: str) -> set[str]:
        """Extract all `@trace(ID)` tags embedded in source comments.

        Args:
            code: The raw source code of the file.

        Returns:
            A set of strings containing the exact trace IDs (e.g. {'FR-1', 'NFR-2'}).
        """

    @abstractmethod
    def extract_imports(self, code: str) -> list[str]:
        """Extract all module import paths from the file.

        Returns:
            A list of string representation of imported module paths, deduplicated.
        """

    @abstractmethod
    def get_binary_ignore_patterns(self) -> list[str]:
        """Return binary file extensions to completely exclude from pure-logic Tree Sitter parsers."""

    @abstractmethod
    def get_default_directory_ignores(self) -> list[str]:
        """Return default directory paths to scaffold into .specweaverignore (e.g. ['target/', 'node_modules/'])."""

    def supported_intents(self) -> list[str]:
        """Return a list of operation intents supported by this parser.
        Default is all standard operations. Can be overridden by specific languages to prune capabilities.
        """
        return [
            "skeleton",
            "symbol",
            "symbol_body",
            "list",
            "replace",
            "replace_body",
            "add",
            "delete",
            "traceability",
            "imports",
            "framework_markers",
        ]

    def supported_parameters(self) -> list[str]:
        """Return a list of optional parameters supported by this parser.
        Default is all parameters. Can be overridden to prune unsupported filters.
        """
        return ["visibility", "decorator_filter"]

    @abstractmethod
    def replace_symbol(self, code: str, symbol_name: str, new_code: str) -> str:
        """Replace the entire symbol wrapper (decorators, signature, body)."""

    @abstractmethod
    def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:
        """Replace only the inner execution block of a symbol."""

    @abstractmethod
    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        """Add a new symbol to the file or to a target parent symbol."""

    @abstractmethod
    def delete_symbol(self, code: str, symbol_name: str) -> str:
        """Remove a symbol completely from the file."""


# ---------------------------------------------------------------------------
# Scenario Pipeline Interfaces (Feature 3.28 SF-B2)
# ---------------------------------------------------------------------------


class ScenarioConverterInterface(ABC):
    """Language-specific converter from ``ScenarioSet`` to test file content.

    Mechanical (non-LLM). Produces language-native parametrized test files
    with ``# @trace(FR-X)`` tags for C09 compatibility.

    Each implementation fully owns the output path convention for its language.
    The handler calls ``output_path()`` and writes to the returned location —
    zero language awareness is required in the handler.
    """

    @abstractmethod
    def convert(self, scenario_set: object, stem: str | None = None) -> str:
        """Convert a ``ScenarioSet`` to test file content.

        Args:
            scenario_set: The scenarios to convert.

        Returns:
            The complete test file content as a string.
        """

    @abstractmethod
    def output_path(self, stem: str, project_root: Path) -> Path:
        """Return the full absolute output path for the generated test file.

        Encodes the language's build-tool-enforced test convention:

        - **Python**: ``project_root/scenarios/generated/test_{stem}_scenarios.py``
        - **Java**: ``project_root/src/test/java/scenarios/generated/{Stem}ScenariosTest.java``
        - **Kotlin**: ``project_root/src/test/kotlin/scenarios/generated/{Stem}ScenariosTest.kt``
        - **TypeScript**: ``project_root/scenarios/generated/{stem}.scenarios.test.ts``
        - **Rust**: ``project_root/tests/{stem}_scenarios.rs``

        Args:
            stem: Component name  (e.g. ``'payment'``).
            project_root: Absolute path to the project root directory.

        Returns:
            Absolute ``Path`` to write the generated test file.
        """


class StackTraceFilterInterface(ABC):
    """Strips scenario test file frames from stack traces by language.

    Used by the Arbiter (SF-C) to produce coding agent feedback that contains
    zero scenario vocabulary — only the coding agent's own source frames.

    The scenario frame marker for each language is derived directly from the
    ``output_path()`` convention in ``ScenarioConverterInterface``:

    - **Python / TypeScript**: ``scenarios/generated/`` in the path string
    - **Java / Kotlin**: ``scenarios.generated.`` package prefix in JVM frame
    - **Rust**: ``_scenarios::`` module segment in frame symbol
    """

    @abstractmethod
    def filter(self, stack_trace: str) -> str:
        """Remove scenario file frames; preserve source code frames.

        Args:
            stack_trace: Raw stack trace text from a failing test.

        Returns:
            Filtered stack trace with all scenario frames removed.
        """

    @abstractmethod
    def is_scenario_frame(self, line: str) -> bool:
        """Return ``True`` if this line is from a scenario test file's frame."""
