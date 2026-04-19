# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Language analyzers for context.yaml auto-inference.

Provides a language-agnostic interface (LanguageAnalyzer ABC) with concrete
implementations for Python, Java, Kotlin, Rust, and TypeScript.
Powered by Tree-Sitter extractions from workspace/parsers.

AnalyzerFactory auto-detects the language from file extensions in a directory
and returns the appropriate analyzer. Callers never need to care about the
language — they just use the interface.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.workspace.parsers.interfaces import CodeStructureInterface

from specweaver.workspace.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.parsers.typescript.codestructure import TypeScriptCodeStructure

logger = logging.getLogger(__name__)

# Known standard library top-level modules (subset for heuristic).
# Used to distinguish external vs internal imports.
_STDLIB_TOP_MODULES = frozenset(
    {
        "__future__",
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "builtins",
        "calendar",
        "codecs",
        "collections",
        "concurrent",
        "configparser",
        "contextlib",
        "copy",
        "csv",
        "ctypes",
        "dataclasses",
        "datetime",
        "decimal",
        "difflib",
        "dis",
        "email",
        "encodings",
        "enum",
        "errno",
        "faulthandler",
        "fileinput",
        "fnmatch",
        "fractions",
        "ftplib",
        "functools",
        "gc",
        "getpass",
        "gettext",
        "glob",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "importlib",
        "inspect",
        "io",
        "ipaddress",
        "itertools",
        "json",
        "keyword",
        "linecache",
        "locale",
        "logging",
        "lzma",
        "math",
        "mimetypes",
        "multiprocessing",
        "numbers",
        "operator",
        "os",
        "pathlib",
        "pdb",
        "pickle",
        "pkgutil",
        "platform",
        "pprint",
        "profile",
        "pstats",
        "py_compile",
        "queue",
        "random",
        "re",
        "readline",
        "reprlib",
        "runpy",
        "sched",
        "secrets",
        "select",
        "shelve",
        "shlex",
        "shutil",
        "signal",
        "site",
        "smtplib",
        "socket",
        "socketserver",
        "sqlite3",
        "ssl",
        "stat",
        "statistics",
        "string",
        "struct",
        "subprocess",
        "sys",
        "sysconfig",
        "tempfile",
        "test",
        "textwrap",
        "threading",
        "time",
        "timeit",
        "token",
        "tokenize",
        "tomllib",
        "trace",
        "traceback",
        "tracemalloc",
        "turtle",
        "types",
        "typing",
        "unicodedata",
        "unittest",
        "urllib",
        "uuid",
        "venv",
        "warnings",
        "wave",
        "weakref",
        "webbrowser",
        "xml",
        "xmlrpc",
        "zipfile",
        "zipimport",
        "zlib",
    }
)


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

        Returns full dotted module paths (e.g., 'specweaver.core.config.settings').
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

    @abstractmethod
    def get_binary_ignore_patterns(self) -> list[str]:
        """Get polyglot binary suppression patterns (e.g., *.pyc)."""
        ...

    @abstractmethod
    def get_default_directory_ignores(self) -> list[str]:
        """Get polyglot directory suppression patterns (e.g., target/, node_modules/)."""
        ...



class TreeSitterAnalyzerBase(LanguageAnalyzer):
    """Base class for language analyzers powered by Tree-Sitter parsers."""

    def __init__(self, parser: CodeStructureInterface, ext: str) -> None:
        self.parser = parser
        self.ext = ext

    def detect(self, directory: Path) -> bool:
        """Check if directory contains any files of this extension."""
        return any(directory.glob(f"*{self.ext}"))

    def extract_imports(self, directory: Path) -> list[str]:
        """Extract all imports, deduplicated, using the underlying tree-sitter parser."""
        imports: set[str] = set()
        for file_path in directory.glob(f"*{self.ext}"):
            try:
                code_text = file_path.read_text(encoding="utf-8")
                for imp in self.parser.extract_imports(code_text):
                    if imp:
                        imports.add(imp)
            except Exception as e:
                logger.debug(f"Failed to extract imports from {file_path}: {e}")
        return sorted(list(imports))

    def extract_public_symbols(self, directory: Path) -> list[str]:
        """Extract public symbols using the underlying tree-sitter parser."""
        symbols: set[str] = set()
        for file_path in directory.glob(f"*{self.ext}"):
            try:
                code_text = file_path.read_text(encoding="utf-8")
                for sym in self.parser.list_symbols(code_text, visibility=["public"]):
                    symbols.add(sym)
            except Exception as e:
                logger.debug(f"Failed to extract symbols from {file_path}: {e}")
        return sorted(list(symbols))

    def infer_archetype(self, directory: Path) -> str:
        """Heuristic: external imports → adapter, otherwise → pure-logic."""
        imports = self.extract_imports(directory)
        if not imports:
            return "pure-logic"

        for imp in imports:
            top = self._get_import_prefix(imp)
            if self._is_external(top):
                logger.debug(
                    "Inferred archetype 'adapter' for %s (external import: %s)", directory.name, top
                )
                return "adapter"

        return "pure-logic"

    def get_binary_ignore_patterns(self) -> list[str]:
        """Delegates binary ignores to the underlying code structure parser."""
        return self.parser.get_binary_ignore_patterns()

    def get_default_directory_ignores(self) -> list[str]:
        """Delegates directory ignores to the underlying code structure parser."""
        return self.parser.get_default_directory_ignores()

    @abstractmethod
    def _get_import_prefix(self, imp: str) -> str:
        """Extract the root module/namespace from the import string for checking."""
        ...

    @abstractmethod
    def _is_external(self, top: str) -> bool:
        """Return True if the root module belongs to an external library/framework."""
        ...


class PythonAnalyzer(TreeSitterAnalyzerBase):
    def __init__(self) -> None:
        super().__init__(PythonCodeStructure(), ".py")

    def extract_purpose(self, directory: Path) -> str | None:
        init_file = directory / "__init__.py"
        if not init_file.is_file():
            return None
        text = init_file.read_text(encoding="utf-8").strip()
        if text.startswith('"""'):
            parts = text[3:].split('"""')
            if parts:
                return parts[0].strip().split("\n")[0]
        return None

    def _get_import_prefix(self, imp: str) -> str:
        return imp.split(".")[0]

    def _is_external(self, top: str) -> bool:
        return top not in _STDLIB_TOP_MODULES and not top.startswith("specweaver")


class JavaAnalyzer(TreeSitterAnalyzerBase):
    def __init__(self) -> None:
        super().__init__(JavaCodeStructure(), ".java")

    def extract_purpose(self, directory: Path) -> str | None:
        return None

    def _get_import_prefix(self, imp: str) -> str:
        return imp

    def _is_external(self, top: str) -> bool:
        return not (
            top.startswith("java.") or top.startswith("javax.") or top.startswith("specweaver")
        )


class KotlinAnalyzer(TreeSitterAnalyzerBase):
    def __init__(self) -> None:
        super().__init__(KotlinCodeStructure(), ".kt")

    def extract_purpose(self, directory: Path) -> str | None:
        return None

    def _get_import_prefix(self, imp: str) -> str:
        return imp

    def _is_external(self, top: str) -> bool:
        return not (
            top.startswith("kotlin.")
            or top.startswith("java.")
            or top.startswith("javax.")
            or top.startswith("specweaver")
        )


class RustAnalyzer(TreeSitterAnalyzerBase):
    def __init__(self) -> None:
        super().__init__(RustCodeStructure(), ".rs")

    def extract_purpose(self, directory: Path) -> str | None:
        return None

    def _get_import_prefix(self, imp: str) -> str:
        return imp.split("::")[0]

    def _is_external(self, top: str) -> bool:
        return top not in ("std", "core", "alloc", "specweaver")


class TypeScriptAnalyzer(TreeSitterAnalyzerBase):
    def __init__(self) -> None:
        super().__init__(TypeScriptCodeStructure(), ".ts")

    def extract_purpose(self, directory: Path) -> str | None:
        return None

    def _get_import_prefix(self, imp: str) -> str:
        return imp

    def _is_external(self, top: str) -> bool:
        if top.startswith(".") or top.startswith("/"):
            return False
        builtins = {
            "fs",
            "path",
            "crypto",
            "os",
            "util",
            "events",
            "http",
            "stream",
            "buffer",
            "child_process",
            "assert",
            "url",
            "console",
        }
        if top.startswith("node:") or top in builtins:
            return False
        return not (top.startswith("specweaver") or top.startswith("src/"))


class AnalyzerFactory:
    """Auto-detect language from file extensions, return appropriate analyzer."""

    _analyzers: ClassVar[list[LanguageAnalyzer]] = [
        PythonAnalyzer(),
        JavaAnalyzer(),
        KotlinAnalyzer(),
        RustAnalyzer(),
        TypeScriptAnalyzer(),
    ]

    @classmethod
    def for_directory(cls, directory: Path) -> LanguageAnalyzer | None:
        """Return the first analyzer that detects its language in the directory.

        Returns None if no known language is detected.
        """
        for analyzer in cls._analyzers:
            if analyzer.detect(directory):
                logger.debug(
                    "AnalyzerFactory resolved %s for %s", type(analyzer).__name__, directory
                )
                return analyzer
        logger.debug("No analyzer detected for %s", directory)
        return None

    @classmethod
    def get_all_analyzers(cls) -> list[LanguageAnalyzer]:
        """Return all registered language analyzers globally for polyglot union aggregations."""
        return cls._analyzers
