from unittest.mock import MagicMock

import pytest

from specweaver.loom.atoms.base import AtomResult, AtomStatus

# Will fail to import because we haven't created it yet!
from specweaver.loom.tools.code_structure.tool import CodeStructureTool, CodeStructureToolError
from specweaver.loom.tools.filesystem.models import AccessMode, FolderGrant


def test_tool_init_invalid_role() -> None:
    atom = MagicMock()
    with pytest.raises(ValueError, match="Unknown role"):
        CodeStructureTool(atom=atom, role="invalid_role", grants=[])


def test_tool_read_file_structure_requires_intent() -> None:
    atom = MagicMock()
    # Planner doesn't naturally have "read_symbol_body"
    tool = CodeStructureTool(
        atom=atom,
        role="planner",
        grants=[FolderGrant(path="", mode=AccessMode.READ, recursive=True)],
    )

    with pytest.raises(CodeStructureToolError, match="not allowed for role"):
        tool.read_symbol_body("test.py", "MyClass")


def test_tool_read_file_structure_blocked_by_grant() -> None:
    atom = MagicMock()
    # Grant ONLY to 'src/other'
    grants = [FolderGrant(path="src/other", mode=AccessMode.READ, recursive=True)]
    tool = CodeStructureTool(atom=atom, role="reviewer", grants=grants)

    result = tool.read_file_structure("src/test.py")
    assert result.status == "error"
    assert "No grant covers path" in result.message


def test_tool_read_file_structure_success() -> None:
    atom = MagicMock()
    atom.run.return_value = AtomResult(
        status=AtomStatus.SUCCESS, message="Success", exports={"structure": "def main():"}
    )

    tool = CodeStructureTool(
        atom=atom,
        role="reviewer",
        grants=[FolderGrant(path="", mode=AccessMode.READ, recursive=True)],
    )

    result = tool.read_file_structure("test.py")
    assert result.status == "success"
    assert result.data["structure"] == "def main():"

    # Verify atom run intent
    atom.run.assert_called_once_with({"intent": "read_file_structure", "path": "test.py"})


def test_tool_definitions_filters_by_role() -> None:
    atom = MagicMock()
    tool = CodeStructureTool(atom=atom, role="planner", grants=[])
    defs = tool.definitions()

    names = [d.name for d in defs]
    assert "read_file_structure" in names
    assert "read_symbol_body" not in names  # Planner doesn't get this


def test_tool_intents_propagate_to_atom() -> None:
    atom = MagicMock()
    atom.run.return_value = AtomResult(
        status=AtomStatus.SUCCESS, message="OK", exports={"symbols": ["A"]}
    )
    tool = CodeStructureTool(
        atom=atom,
        role="implementer",
        grants=[FolderGrant(path="", mode=AccessMode.READ, recursive=True)],
    )

    tool.list_symbols("test.py", visibility=["public"])
    atom.run.assert_called_with(
        {"intent": "list_symbols", "path": "test.py", "visibility": ["public"]}
    )

    atom.run.return_value = AtomResult(
        status=AtomStatus.SUCCESS, message="OK", exports={"symbol": "def func():"}
    )
    tool.read_symbol("test.py", "func")
    atom.run.assert_called_with({"intent": "read_symbol", "path": "test.py", "symbol_name": "func"})

    atom.run.return_value = AtomResult(
        status=AtomStatus.SUCCESS, message="OK", exports={"body": "pass"}
    )
    tool.read_symbol_body("test.py", "func")
    atom.run.assert_called_with(
        {"intent": "read_symbol_body", "path": "test.py", "symbol_name": "func"}
    )


def test_tool_normalize_windows_paths() -> None:
    atom = MagicMock()
    tool = CodeStructureTool(atom=atom, role="implementer", grants=[])

    assert tool._normalize_path("C:\\test\\dir") == "C:/test/dir"
    assert tool._normalize_path("test\\dir") == "test/dir"
    assert tool._normalize_path(".") == ""


def test_tool_resolve_mode_priority_and_recursive() -> None:
    atom = MagicMock()
    # Path logic prioritizes FULL over READ exactly
    grants = [
        FolderGrant(path="src", mode=AccessMode.READ, recursive=True),
        FolderGrant(path="src/tests", mode=AccessMode.WRITE, recursive=True),
        FolderGrant(path="src/tests/e2e", mode=AccessMode.FULL, recursive=True),
    ]
    tool = CodeStructureTool(atom=atom, role="implementer", grants=grants)

    assert tool._resolve_mode("src/random.py") == AccessMode.READ
    assert tool._resolve_mode("src/tests/random.py") == AccessMode.WRITE
    assert tool._resolve_mode("src/tests/e2e/file.py") == AccessMode.FULL

    # No recursion case
    non_recursive = [FolderGrant(path="exact", mode=AccessMode.FULL, recursive=False)]
    tool_nr = CodeStructureTool(atom=atom, role="implementer", grants=non_recursive)
    assert tool_nr._resolve_mode("exact") == AccessMode.FULL
    assert tool_nr._resolve_mode("exact/child.py") == AccessMode.FULL
    assert tool_nr._resolve_mode("exact/child/grandchild.py") is None


def test_tool_execution_serialization() -> None:
    """ToolResult gracefully packages nested structures and wraps errors."""
    atom = MagicMock()
    tool = CodeStructureTool(
        atom=atom,
        role="implementer",
        grants=[FolderGrant(path="", mode=AccessMode.READ, recursive=True)],
    )

    atom.run.return_value = AtomResult(status=AtomStatus.FAILED, message="Some error bubbled")
    res1 = tool.read_symbol("test.py", "FailTarget")
    assert res1.status == "error"
    assert res1.message == "Some error bubbled"

    atom.run.return_value = AtomResult(
        status=AtomStatus.SUCCESS, message="OK", exports={"symbol": "def TestTarget(): pass"}
    )
    res2 = tool.read_symbol("test.py", "TestTarget")
    assert res2.status == "success"
    assert res2.data["symbol"] == "def TestTarget(): pass"


def test_tool_mutation_intents_blocked_by_read_grant() -> None:
    atom = MagicMock()
    # implementer is allowed the intent, but if we only give AccessMode.READ, it should block
    tool = CodeStructureTool(
        atom=atom,
        role="implementer",
        grants=[FolderGrant(path="", mode=AccessMode.READ, recursive=True)],
    )

    res = tool.replace_symbol("test.py", "Target", "pass")
    assert res.status == "error"
    assert "Insufficient permissions" in res.message
    assert "read" in res.message.lower()
    atom.run.assert_not_called()


def test_tool_mutation_intents_success_with_write_grant() -> None:
    atom = MagicMock()
    atom.run.return_value = AtomResult(status=AtomStatus.SUCCESS, message="Replaced", exports={})
    tool = CodeStructureTool(
        atom=atom,
        role="implementer",
        grants=[FolderGrant(path="", mode=AccessMode.WRITE, recursive=True)],
    )

    res = tool.replace_symbol("test.py", "Target", "pass")
    assert res.status == "success"
    atom.run.assert_called_with(
        {"intent": "replace_symbol", "path": "test.py", "symbol_name": "Target", "new_code": "pass"}
    )

    tool.add_symbol("test.py", "fn added() {}")
    atom.run.assert_called_with(
        {
            "intent": "add_symbol",
            "path": "test.py",
            "new_code": "fn added() {}",
            "target_parent": None,
        }
    )

    tool.delete_symbol("test.py", "Target")
    atom.run.assert_called_with(
        {"intent": "delete_symbol", "path": "test.py", "symbol_name": "Target"}
    )
