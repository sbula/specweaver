# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Language analyzers for context.yaml auto-inference.

Provides a language-agnostic interface (LanguageAnalyzer ABC) with concrete
implementations (PythonAnalyzer first, expandable to Java, Kotlin, Rust,
TypeScript, C++, SQL, etc.).

AnalyzerFactory auto-detects the language from file extensions in a directory
and returns the appropriate analyzer. Callers never need to care about the
language — they just use the interface.
"""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

# Known standard library top-level modules (subset for heuristic).
# Used to distinguish external vs internal imports.
_STDLIB_TOP_MODULES = frozenset({
    "__future__", "abc", "argparse", "ast", "asyncio", "base64",
    "builtins", "calendar", "codecs", "collections", "concurrent",
    "configparser", "contextlib", "copy", "csv", "ctypes", "dataclasses",
    "datetime", "decimal", "difflib", "dis", "email", "encodings",
    "enum", "errno", "faulthandler", "fileinput", "fnmatch",
    "fractions", "ftplib", "functools", "gc", "getpass", "gettext",
    "glob", "gzip", "hashlib", "heapq", "hmac", "html", "http",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "linecache", "locale", "logging", "lzma", "math",
    "mimetypes", "multiprocessing", "numbers", "operator", "os",
    "pathlib", "pdb", "pickle", "pkgutil", "platform", "pprint",
    "profile", "pstats", "py_compile", "queue", "random", "re",
    "readline", "reprlib", "runpy", "sched", "secrets", "select",
    "shelve", "shlex", "shutil", "signal", "site", "smtplib",
    "socket", "socketserver", "sqlite3", "ssl", "stat", "statistics",
    "string", "struct", "subprocess", "sys", "sysconfig", "tempfile",
    "test", "textwrap", "threading", "time", "timeit", "token",
    "tokenize", "tomllib", "trace", "traceback", "tracemalloc",
    "turtle", "types", "typing", "unicodedata", "unittest", "urllib",
    "uuid", "venv", "warnings", "wave", "weakref", "webbrowser",
    "xml", "xmlrpc", "zipfile", "zipimport", "zlib",
})


class LanguageAnalyzer(ABC):
    """Abstract interface for extracting context.yaml-relevant info from source.

    Each concrete implementation handles one programming language.
    AnalyzerFactory selects the right one based on file extensions.
    """

    @abstractmethod
    def detect(self, directory: Path) -> bool:
        """Return True if this directory contains files of this language."""
        ...

    @abstractmethod
    def extract_purpose(self, directory: Path) -> str | None:
        """Extract a one-sentence purpose from module-level docstrings.

        Returns None if no purpose can be determined.
        """
        ...

    @abstractmethod
    def extract_imports(self, directory: Path) -> list[str]:
        """Extract all imported module names (top-level, deduplicated).

        Returns full dotted module paths (e.g., 'specweaver.config.settings').
        """
        ...

    @abstractmethod
    def extract_public_symbols(self, directory: Path) -> list[str]:
        """Extract public symbol names (classes, functions, constants).

        Respects __all__ if defined. Otherwise, excludes _private names.
        """
        ...

    @abstractmethod
    def infer_archetype(self, directory: Path) -> str:
        """Heuristically infer the archetype from code patterns.

        Returns one of the context.yaml archetype values:
        'pure-logic', 'adapter', 'facade', 'orchestrator', etc.
        """
        ...


class PythonAnalyzer(LanguageAnalyzer):
    """Python-specific analyzer.

    - Purpose: from __init__.py module-level docstring
    - Imports: AST-parsed from all .py files
    - Public symbols: __all__ or non-underscore class/function names
    - Archetype: heuristic based on import patterns
    """

    def detect(self, directory: Path) -> bool:
        """Check if directory contains any .py files."""
        return any(directory.glob("*.py"))

    def extract_purpose(self, directory: Path) -> str | None:
        """Extract docstring from __init__.py."""
        init_file = directory / "__init__.py"
        if not init_file.is_file():
            return None

        try:
            tree = ast.parse(init_file.read_text(encoding="utf-8"))
        except SyntaxError:
            return None

        docstring = ast.get_docstring(tree)
        if docstring:
            # Take just the first line/sentence
            first_line = docstring.strip().split("\n")[0].strip()
            return first_line if first_line else None
        return None

    def extract_imports(self, directory: Path) -> list[str]:
        """Extract all imports from .py files, deduplicated."""
        seen: set[str] = set()

        for py_file in directory.glob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        seen.add(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    seen.add(node.module)

        return sorted(seen)

    def extract_public_symbols(self, directory: Path) -> list[str]:
        """Extract public symbols, preferring __all__ if defined."""
        # First check __init__.py for __all__
        all_symbols = self._extract_all_from_init(directory)
        if all_symbols is not None:
            return sorted(all_symbols)

        # Fallback: scan all .py files for public class/function names
        symbols: set[str] = set()
        for py_file in directory.glob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                    symbols.add(node.name)

        return sorted(symbols)

    def infer_archetype(self, directory: Path) -> str:
        """Heuristic: external imports → adapter, otherwise → pure-logic."""
        imports = self.extract_imports(directory)
        if not imports:
            return "pure-logic"

        for imp in imports:
            top = imp.split(".")[0]
            if top not in _STDLIB_TOP_MODULES and not top.startswith("specweaver"):
                return "adapter"

        return "pure-logic"

    @staticmethod
    def _extract_all_from_init(directory: Path) -> list[str] | None:
        """Extract __all__ list from __init__.py, if defined."""
        init_file = directory / "__init__.py"
        if not init_file.is_file():
            return None

        try:
            tree = ast.parse(init_file.read_text(encoding="utf-8"))
        except SyntaxError:
            return None

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple)):
                            return [
                                elt.value
                                for elt in node.value.elts
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                            ]
        return None


class AnalyzerFactory:
    """Auto-detect language from file extensions, return appropriate analyzer.

    Currently supports Python. Additional languages can be added by
    creating new LanguageAnalyzer subclasses and registering them here.
    """

    _analyzers: ClassVar[list[LanguageAnalyzer]] = [
        PythonAnalyzer(),
        # Future: JavaAnalyzer(), KotlinAnalyzer(), RustAnalyzer(),
        # TypeScriptAnalyzer(), CppAnalyzer(), SqlAnalyzer()
    ]

    @classmethod
    def for_directory(cls, directory: Path) -> LanguageAnalyzer | None:
        """Return the first analyzer that detects its language in the directory.

        Returns None if no known language is detected.
        """
        for analyzer in cls._analyzers:
            if analyzer.detect(directory):
                return analyzer
        return None
