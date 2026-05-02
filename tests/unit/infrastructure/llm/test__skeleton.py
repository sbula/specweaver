# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

from specweaver.infrastructure.llm._skeleton import extract_ast_skeleton


class TestSkeletonExtractor:
    """Verify fallback and mapping behaviors of the internal skeleton parser."""

    def test_extract_skeleton_fallback_on_unsupported_parser(self) -> None:
        """When the extension is unsupported, extract_skeleton gracefully returns original code."""
        css_content = ".class { color: red; }"
        result = extract_ast_skeleton(Path("styles.css"), css_content)
        assert css_content == result

    def test_extract_skeleton_fallback_on_parse_exception(self, monkeypatch) -> None:
        """If the AST parser explicitly raises an error, extract_skeleton gracefully falls back."""
        broken_content = "def invalid_syntax(@#*&):"

        # We manually monkeypatch parser mapping to ensure a fatal extraction error
        from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure

        def mock_extract(*args, **kwargs):
            raise RuntimeError("Fatal parse error")

        monkeypatch.setattr(PythonCodeStructure, "extract_skeleton", mock_extract)

        result = extract_ast_skeleton(Path("broken.py"), broken_content)
        assert broken_content == result
