# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import pytest

from specweaver.workspace.parsers.markdown.codestructure import MarkdownCodeStructure


@pytest.fixture
def parser() -> MarkdownCodeStructure:
    return MarkdownCodeStructure()


def test_extract_skeleton_success(parser: MarkdownCodeStructure) -> None:
    code = "# H1\nSome text\n## H2\nMore text\n### H3\n"
    res = parser.extract_skeleton(code)
    assert "# H1" in res
    assert "## H2" in res
    assert "### H3" in res
    assert "Some text" not in res


def test_extract_skeleton_empty(parser: MarkdownCodeStructure) -> None:
    assert parser.extract_skeleton("   ") == "   "


def test_extract_symbol_success(parser: MarkdownCodeStructure) -> None:
    code = "# H1\n\nsymbol content\n"
    assert parser.extract_symbol(code, "H1") == "# H1\n\nsymbol content\n"
