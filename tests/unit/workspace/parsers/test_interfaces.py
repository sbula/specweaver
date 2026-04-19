# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from typing import Any

import pytest

from specweaver.workspace.parsers.interfaces import CodeStructureInterface


def test_code_structure_interface_enforces_abstract_methods() -> None:  # noqa: C901
    """Verify that any subclass must accurately implement the binary and directory ignore arrays."""

    class IncompleteParser(CodeStructureInterface):
        # We purposely do not implement get_binary_ignore_patterns and get_default_directory_ignores
        parser: Any = None
        def extract_skeleton(self, code: str) -> str: return ""
        def extract_symbol(self, code: str, symbol_name: str) -> str: return ""
        def extract_symbol_body(self, code: str, symbol_name: str) -> str: return ""
        def list_symbols(self, code: str, visibility: list[str] | None = None, decorator_filter: str | None = None) -> list[str]: return []
        def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]: return {}
        def extract_imports(self, code: str) -> list[str]: return []
        def replace_symbol(self, code: str, symbol_name: str, new_code: str) -> str: return ""
        def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str: return ""
        def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str: return ""
        def delete_symbol(self, code: str, symbol_name: str) -> str: return ""

    with pytest.raises(TypeError, match="Can't instantiate abstract class IncompleteParser without an implementation for abstract methods"):
        parser = IncompleteParser()  # type: ignore[abstract]

    class CompleteParser(IncompleteParser):
        def get_binary_ignore_patterns(self) -> list[str]:
            return ["*.mock"]

        def get_default_directory_ignores(self) -> list[str]:
            return ["mock_modules/"]

        def extract_traceability_tags(self, code: str) -> set[str]:
            return set()

    parser = CompleteParser()
    assert parser.get_binary_ignore_patterns() == ["*.mock"]
    assert parser.get_default_directory_ignores() == ["mock_modules/"]
