from unittest.mock import MagicMock

from specweaver.core.loom.atoms.base import AtomStatus

# Will fail to import because we haven't created it yet!
from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom
from specweaver.core.loom.commons.filesystem.executor import ExecutorResult


def test_atom_unsupported_intent() -> None:
    executor = MagicMock()
    atom = CodeStructureAtom(executor)

    result = atom.run({"intent": "invalid_intent", "path": "test.py"})
    assert result.status == AtomStatus.FAILED
    assert "Unsupported code structure intent" in result.message


def test_atom_unsupported_language_fallback() -> None:
    executor = MagicMock()
    # Mock reading a markdown file
    executor.read.return_value = ExecutorResult(status="success", data="# README")
    atom = CodeStructureAtom(executor)

    result = atom.run({"intent": "read_file_structure", "path": "README.md"})
    assert result.status == AtomStatus.FAILED
    assert "AST Structure Extraction not supported" in result.message


def test_atom_read_file_structure_success() -> None:
    executor = MagicMock()
    py_code = "def my_func():\n    print('hello')\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor)

    result = atom.run({"intent": "read_file_structure", "path": "test.py"})
    assert result.status == AtomStatus.SUCCESS
    assert "def my_func():" in result.exports["structure"]


def test_atom_read_symbol_success() -> None:
    executor = MagicMock()
    py_code = "class MyClass:\n    pass\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor)

    result = atom.run({"intent": "read_symbol", "path": "test.py", "symbol_name": "MyClass"})
    assert result.status == AtomStatus.SUCCESS
    assert "class MyClass:\n    pass" in result.exports["symbol"]


def test_atom_read_symbol_body_success() -> None:
    executor = MagicMock()
    py_code = "def logic():\n    return 42\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor)

    result = atom.run({"intent": "read_symbol_body", "path": "test.py", "symbol_name": "logic"})
    assert result.status == AtomStatus.SUCCESS
    assert "return 42" in result.exports["body"]


def test_atom_list_symbols_success() -> None:
    executor = MagicMock()
    py_code = "class A: pass\ndef b(): pass\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor)

    result = atom.run({"intent": "list_symbols", "path": "test.py", "visibility": ["public"]})
    assert result.status == AtomStatus.SUCCESS
    assert result.exports["symbols"] == ["A", "b"]


def test_atom_file_read_error() -> None:
    executor = MagicMock()
    # Mocking failure from file execution
    executor.read.return_value = ExecutorResult(status="error", error="Permission Denied")
    atom = CodeStructureAtom(executor)

    result = atom.run({"intent": "read_file_structure", "path": "no_access.py"})
    assert result.status == AtomStatus.FAILED
    assert result.message == "Permission Denied"


def test_atom_bubble_up_code_structure_error() -> None:
    executor = MagicMock()
    # Provide valid file, but cause the parser to fail
    executor.read.return_value = ExecutorResult(status="success", data="def existing(): pass")
    atom = CodeStructureAtom(executor)

    # We use python file but request symbol that does not exist
    result = atom.run({"intent": "read_symbol", "path": "wrong.py", "symbol_name": "Ghost"})
    assert result.status == AtomStatus.FAILED
    assert "Symbol 'Ghost' not found" in result.message


def test_atom_missing_path() -> None:
    executor = MagicMock()
    atom = CodeStructureAtom(executor)
    result = atom.run({"intent": "read_file_structure"})
    assert result.status == AtomStatus.FAILED
    assert "Missing required fields" in result.message
