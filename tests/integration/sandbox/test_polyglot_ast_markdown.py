# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from typing import Any
from unittest.mock import MagicMock

from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom


def _run_atom(
    intent: str, path: str, context: dict[str, Any], file_system_simulator: dict[str, str]
) -> Any:
    """Mock the file system executor injected to the CodeStructureAtom."""
    executor = MagicMock()
    executor.read.side_effect = lambda p: MagicMock(
        status="success", data=file_system_simulator.get(p, "")
    )

    def _mock_write(p: str, data: str, **kwargs: Any) -> MagicMock:
        file_system_simulator[p] = data
        return MagicMock(status="success")

    executor.write.side_effect = _mock_write

    atom = CodeStructureAtom(executor)
    res = atom.run({"intent": intent, "path": path, **context})
    return res


def test_markdown_extract_skeleton() -> None:
    """E2E assert that CodeStructureAtom gracefully extracts structural Markdown headers."""
    markdown_doc = """# Main Title

Some description here.

## 1. Purpose
The purpose of this component is to validate.

## 2. Boundaries
This component bounded safely.
"""

    res = _run_atom("read_file_structure", "spec.md", {}, {"spec.md": markdown_doc})

    assert res.status.value == "SUCCESS"

    skeleton = res.exports["structure"]
    assert "# Main Title" in skeleton
    assert "S ... " in skeleton
    assert "## 1. Purpose" in skeleton
    assert "T ... " in skeleton
    assert "## 2. Boundaries" in skeleton


def test_markdown_symbol_extraction() -> None:
    from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure

    atom = MarkdownCodeStructure()
    code = "# h1\n\nsymbol content\n\n## sub\n"

    assert atom.extract_symbol(code, "h1") == "# h1\n\nsymbol content\n\n## sub\n"
    assert atom.extract_symbol_body(code, "h1") == "\nsymbol content\n\n## sub\n"


def test_markdown_mutators() -> None:
    from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure

    atom = MarkdownCodeStructure()
    code = "# h1\n\nold text\n\n## sub\n"

    res = atom.replace_symbol(code, "h1", "# h1 modified\n\nnew text\n")
    assert res == "# h1 modified\n\nnew text\n"

    res_body = atom.replace_symbol_body(code, "h1", "\nnew text body\n")
    assert res_body == "# h1\n\nnew text body\n"

    res_delete = atom.delete_symbol(code, "h1")
    assert res_delete == ""

    res_add = atom.add_symbol(code, None, "## added\n")
    assert res_add == "# h1\n\nold text\n\n## sub\n\n## added\n"


def test_markdown_list_symbols_and_markers() -> None:
    from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure

    atom = MarkdownCodeStructure()
    assert atom.list_symbols("# content\n") == ["content"]
    assert atom.extract_framework_markers("# content\n") == {}


def test_markdown_add_symbol_edge_cases() -> None:
    import pytest

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureError
    from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure

    atom = MarkdownCodeStructure()

    # 1. returns new_code if code is empty
    assert atom.add_symbol("", None, "# h1\n") == "# h1\n"
    assert atom.add_symbol("   \n", None, "# h1\n") == "# h1\n"

    # 2. raises CodeStructureError if target_parent is passed
    with pytest.raises(
        CodeStructureError, match="Markdown does not support injecting into target_parent"
    ):
        atom.add_symbol("# content\n", "parent", "## child\n")

    # 3. appends newlines cleanly
    assert atom.add_symbol("# content", None, "## added") == "# content\n\n## added"
    assert atom.add_symbol("# content\n", None, "## added") == "# content\n\n## added"


def test_markdown_missing_symbols() -> None:
    import pytest

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureError
    from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure

    atom = MarkdownCodeStructure()
    code = "# content\n"

    with pytest.raises(CodeStructureError, match=r"Symbol 'missing' not found.*"):
        atom.extract_symbol(code, "missing")

    with pytest.raises(CodeStructureError, match=r"Symbol 'missing' not found.*"):
        atom.extract_symbol_body(code, "missing")

    with pytest.raises(CodeStructureError, match=r"Symbol 'missing' not found.*"):
        atom.replace_symbol(code, "missing", "foo")

    with pytest.raises(CodeStructureError, match=r"Symbol 'missing' not found.*"):
        atom.replace_symbol_body(code, "missing", "foo")

    with pytest.raises(CodeStructureError, match=r"Symbol 'missing' not found.*"):
        atom.delete_symbol(code, "missing")


def test_markdown_stub_handlers() -> None:
    from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure

    atom = MarkdownCodeStructure()
    code = "# content\n"

    assert atom.extract_traceability_tags(code) == set()
    assert atom.extract_imports(code) == []
    assert atom.get_binary_ignore_patterns() == []
    assert atom.get_default_directory_ignores() == []


def test_markdown_atom_mutate_code() -> None:
    """E2E assert that CodeStructureAtom successfully mutates Markdown files."""
    markdown_doc = "# Main\n\ncontent\n"
    fs = {"spec.md": markdown_doc}

    # Replace
    res_replace = _run_atom(
        "replace_symbol",
        "spec.md",
        {"symbol_name": "Main", "new_code": "# Main modified\n\nnew content\n"},
        fs,
    )
    assert res_replace.status.value == "SUCCESS"
    assert fs["spec.md"] == "# Main modified\n\nnew content\n"

    # Add
    res_add = _run_atom(
        "add_symbol", "spec.md", {"target_parent": None, "new_code": "## Add\n"}, fs
    )
    assert res_add.status.value == "SUCCESS"
    assert fs["spec.md"] == "# Main modified\n\nnew content\n\n## Add\n"
