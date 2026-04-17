# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import json
from typing import Any
from unittest.mock import MagicMock

from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom


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

    # Must be JSON payload representing headers
    try:
        skeleton = json.loads(res.exports["structure"])
    except json.JSONDecodeError:
        raise AssertionError("Markdown skeleton should be returned as JSON formatted string") from None

    assert skeleton["h1"] == ["Main Title"]
    assert "1. Purpose" in skeleton["h2"]
    assert "2. Boundaries" in skeleton["h2"]


def test_markdown_unsupported_symbol_extraction() -> None:
    import pytest

    from specweaver.core.loom.commons.language.interfaces import CodeStructureError
    from specweaver.core.loom.commons.language.markdown.codestructure import MarkdownCodeStructure

    atom = MarkdownCodeStructure()
    with pytest.raises(
        CodeStructureError, match=r"Markdown extraction logic for symbols is not yet implemented\."
    ):
        atom.extract_symbol("# h1", "symbol")

    with pytest.raises(
        CodeStructureError, match=r"Markdown extraction logic for symbols is not yet implemented\."
    ):
        atom.extract_symbol_body("# h1", "symbol")


def test_markdown_unsupported_mutators() -> None:
    import pytest

    from specweaver.core.loom.commons.language.interfaces import CodeStructureError
    from specweaver.core.loom.commons.language.markdown.codestructure import MarkdownCodeStructure

    atom = MarkdownCodeStructure()
    with pytest.raises(CodeStructureError, match=r"Markdown mutators not implemented\."):
        atom.replace_symbol("# h1", "sym", "foo")

    with pytest.raises(CodeStructureError, match=r"Markdown mutators not implemented\."):
        atom.replace_symbol_body("# h1", "sym", "foo")

    with pytest.raises(CodeStructureError, match=r"Markdown mutators not implemented\."):
        atom.delete_symbol("# h1", "sym")

    with pytest.raises(CodeStructureError, match=r"Markdown mutators not implemented\."):
        atom.add_symbol("# h1", "target", "foo")


def test_markdown_list_symbols_and_markers() -> None:
    from specweaver.core.loom.commons.language.markdown.codestructure import MarkdownCodeStructure

    atom = MarkdownCodeStructure()
    assert atom.list_symbols("# content") == []
    assert atom.extract_framework_markers("# content") == {}
