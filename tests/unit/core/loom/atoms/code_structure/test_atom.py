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
    executor.read.return_value = ExecutorResult(status="success", data="Plain text")
    atom = CodeStructureAtom(executor)

    result = atom.run({"intent": "read_file_structure", "path": "README.txt"})
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


def test_atom_extract_framework_markers_success() -> None:
    executor = MagicMock()
    py_code = "def my_func():\n    print('hello')\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor)

    result = atom.run({"intent": "extract_framework_markers", "path": "test.py"})
    assert result.status == AtomStatus.SUCCESS
    assert "my_func" in result.exports["markers"]


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


def test_atom_active_evaluator_merges_plugins() -> None:
    executor = MagicMock()
    schemas = {
        "spring-boot": {"evaluate": {"annotations": ["@RestController"]}, "intents": {"hide": ["list_symbols"]}},
        "spring-security": {"evaluate": {"annotations": ["@PreAuthorize"]}, "intents": {"hide": ["edit_file"]}}
    }

    # Base archetype only
    atom1 = CodeStructureAtom(executor, evaluator_schemas=schemas, active_archetype="spring-boot")
    assert atom1.active_evaluator["intents"]["hide"] == ["list_symbols"]
    assert "@PreAuthorize" not in atom1.active_evaluator["evaluate"]["annotations"]

    # Archetype + plugin
    atom2 = CodeStructureAtom(executor, evaluator_schemas=schemas, active_archetype="spring-boot", plugins=["spring-security"])

    merged = atom2.active_evaluator
    assert "list_symbols" in merged["intents"]["hide"]
    assert "edit_file" in merged["intents"]["hide"]
    assert "@RestController" in merged["evaluate"]["annotations"]
    assert "@PreAuthorize" in merged["evaluate"]["annotations"]


def test_atom_active_evaluator_deep_merges_nested_schemas() -> None:
    executor = MagicMock()
    schemas = {
        "base": {"settings": {"timeout": 30, "proxy": {"url": "base.com"}}},
        "plugin": {"settings": {"retries": 3, "proxy": {"auth": "bearer"}}}
    }

    atom = CodeStructureAtom(executor, evaluator_schemas=schemas, active_archetype="base", plugins=["plugin"])
    merged = atom.active_evaluator

    assert merged["settings"]["timeout"] == 30
    assert merged["settings"]["retries"] == 3
    assert merged["settings"]["proxy"]["url"] == "base.com"
    assert merged["settings"]["proxy"]["auth"] == "bearer"


def test_atom_active_evaluator_silently_skips_nonexistent_plugins() -> None:
    executor = MagicMock()
    schemas = {
        "generic": {"evaluate": {"annotations": ["@Base"]}}
    }

    atom = CodeStructureAtom(executor, evaluator_schemas=schemas, active_archetype="generic", plugins=["ghost-plugin", "phantom"])
    merged = atom.active_evaluator

    # Should safely just return the base generic evaluation without failing
    assert merged["evaluate"]["annotations"] == ["@Base"]
