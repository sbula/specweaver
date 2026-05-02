from typing import Any
from unittest.mock import MagicMock

from specweaver.core.loom.atoms.base import AtomStatus

# Will fail to import because we haven't created it yet!
from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom
from specweaver.core.loom.commons.filesystem.executor import ExecutorResult


def _get_mock_parsers() -> Any:
    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface

    mock_parser = MagicMock(spec=CodeStructureInterface)
    mock_parser.extract_skeleton.return_value = "def my_func():"
    mock_parser.extract_framework_markers.return_value = {"my_func": {}}
    mock_parser.extract_symbol.return_value = "class MyClass:\n    pass"
    mock_parser.extract_symbol_body.return_value = "return 42"
    mock_parser.list_symbols.return_value = ["A", "b"]
    return {(".py",): mock_parser}


def test_atom_unsupported_intent() -> None:
    executor = MagicMock()
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    result = atom.run({"intent": "invalid_intent", "path": "test.py"})
    assert result.status == AtomStatus.FAILED
    assert "Unsupported code structure intent" in result.message


def test_atom_unsupported_language_fallback() -> None:
    executor = MagicMock()
    # Mock reading a markdown file
    executor.read.return_value = ExecutorResult(status="success", data="Plain text")
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    result = atom.run({"intent": "read_file_structure", "path": "README.txt"})
    assert result.status == AtomStatus.FAILED
    assert "AST Structure Extraction not supported" in result.message


def test_atom_read_file_structure_success() -> None:
    executor = MagicMock()
    py_code = "def my_func():\n    print('hello')\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    result = atom.run({"intent": "read_file_structure", "path": "test.py"})
    assert result.status == AtomStatus.SUCCESS
    assert "def my_func():" in result.exports["structure"]


def test_atom_extract_framework_markers_success() -> None:
    executor = MagicMock()
    py_code = "def my_func():\n    print('hello')\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    result = atom.run({"intent": "extract_framework_markers", "path": "test.py"})
    assert result.status == AtomStatus.SUCCESS
    assert "my_func" in result.exports["markers"]


def test_atom_read_symbol_success() -> None:
    executor = MagicMock()
    py_code = "class MyClass:\n    pass\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    result = atom.run({"intent": "read_symbol", "path": "test.py", "symbol_name": "MyClass"})
    assert result.status == AtomStatus.SUCCESS
    assert "class MyClass:\n    pass" in result.exports["symbol"]


def test_atom_read_symbol_body_success() -> None:
    executor = MagicMock()
    py_code = "def logic():\n    return 42\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    result = atom.run({"intent": "read_symbol_body", "path": "test.py", "symbol_name": "logic"})
    assert result.status == AtomStatus.SUCCESS
    assert "return 42" in result.exports["body"]


def test_atom_list_symbols_success() -> None:
    executor = MagicMock()
    py_code = "class A: pass\ndef b(): pass\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    result = atom.run({"intent": "list_symbols", "path": "test.py", "visibility": ["public"]})
    assert result.status == AtomStatus.SUCCESS
    assert result.exports["symbols"] == ["A", "b"]


def test_atom_file_read_error() -> None:
    executor = MagicMock()
    # Mocking failure from file execution
    executor.read.return_value = ExecutorResult(status="error", error="Permission Denied")
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    result = atom.run({"intent": "read_file_structure", "path": "no_access.py"})
    assert result.status == AtomStatus.FAILED
    assert result.message == "Permission Denied"


def test_atom_bubble_up_code_structure_error() -> None:
    executor = MagicMock()
    # Provide valid file, but cause the parser to fail
    executor.read.return_value = ExecutorResult(status="success", data="def existing(): pass")

    from typing import Any

    from specweaver.workspace.ast.parsers.interfaces import (
        CodeStructureError,
        CodeStructureInterface,
    )

    mock_parser = MagicMock(spec=CodeStructureInterface)
    mock_parser.extract_symbol.side_effect = CodeStructureError("Symbol 'Ghost' not found")
    parsers: Any = {(".py",): mock_parser}

    atom = CodeStructureAtom(executor, parsers=parsers)

    # We use python file but request symbol that does not exist
    result = atom.run({"intent": "read_symbol", "path": "wrong.py", "symbol_name": "Ghost"})
    assert result.status == AtomStatus.FAILED
    assert "Symbol 'Ghost' not found" in result.message


def test_atom_missing_path() -> None:
    executor = MagicMock()
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())
    result = atom.run({"intent": "read_file_structure"})
    assert result.status == AtomStatus.FAILED
    assert "Missing required fields" in result.message


def test_atom_active_evaluator_merges_plugins() -> None:
    executor = MagicMock()
    schemas = {
        "spring-boot": {
            "evaluate": {"annotations": ["@RestController"]},
            "intents": {"hide": ["list_symbols"]},
        },
        "spring-security": {
            "evaluate": {"annotations": ["@PreAuthorize"]},
            "intents": {"hide": ["edit_file"]},
        },
    }

    # Base archetype only
    atom1 = CodeStructureAtom(
        executor,
        evaluator_schemas=schemas,
        active_archetype="spring-boot",
        parsers=_get_mock_parsers(),
    )
    assert atom1.active_evaluator["intents"]["hide"] == ["list_symbols"]
    assert "@PreAuthorize" not in atom1.active_evaluator["evaluate"]["annotations"]

    # Archetype + plugin
    atom2 = CodeStructureAtom(
        executor,
        evaluator_schemas=schemas,
        active_archetype="spring-boot",
        plugins=["spring-security"],
        parsers=_get_mock_parsers(),
    )

    merged = atom2.active_evaluator
    assert "list_symbols" in merged["intents"]["hide"]
    assert "edit_file" in merged["intents"]["hide"]
    assert "@RestController" in merged["evaluate"]["annotations"]
    assert "@PreAuthorize" in merged["evaluate"]["annotations"]


def test_atom_active_evaluator_deep_merges_nested_schemas() -> None:
    executor = MagicMock()
    schemas = {
        "base": {"settings": {"timeout": 30, "proxy": {"url": "base.com"}}},
        "plugin": {"settings": {"retries": 3, "proxy": {"auth": "bearer"}}},
    }

    atom = CodeStructureAtom(
        executor,
        evaluator_schemas=schemas,
        active_archetype="base",
        plugins=["plugin"],
        parsers=_get_mock_parsers(),
    )
    merged = atom.active_evaluator

    assert merged["settings"]["timeout"] == 30
    assert merged["settings"]["retries"] == 3
    assert merged["settings"]["proxy"]["url"] == "base.com"
    assert merged["settings"]["proxy"]["auth"] == "bearer"


def test_atom_active_evaluator_silently_skips_nonexistent_plugins() -> None:
    executor = MagicMock()
    schemas = {"generic": {"evaluate": {"annotations": ["@Base"]}}}

    atom = CodeStructureAtom(
        executor,
        evaluator_schemas=schemas,
        active_archetype="generic",
        plugins=["ghost-plugin", "phantom"],
        parsers=_get_mock_parsers(),
    )
    merged = atom.active_evaluator

    # Should safely just return the base generic evaluation without failing
    assert merged["evaluate"]["annotations"] == ["@Base"]


def test_atom_skeletonize_alias() -> None:
    executor = MagicMock()
    py_code = "def my_func():\n    print('hello')\n"
    executor.read.return_value = ExecutorResult(status="success", data=py_code)
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    result = atom.run({"intent": "skeletonize", "path": "test.py"})
    assert result.status == AtomStatus.SUCCESS
    assert "def my_func():" in result.exports["structure"]


def test_atom_skeletonize_unsupported_language_fallback() -> None:
    executor = MagicMock()
    executor.read.return_value = ExecutorResult(status="success", data="Plain text")
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    result = atom.run({"intent": "skeletonize", "path": "README.txt"})
    assert result.status == AtomStatus.FAILED
    assert "AST Structure Extraction not supported" in result.message


def test_atom_skeletonize_latency_boundary() -> None:
    import time

    executor = MagicMock()
    # Ensure massive payload (mocked, but checking dispatch overhead)
    huge_code = "def my_func():\n    pass\n" * 1000
    executor.read.return_value = ExecutorResult(status="success", data=huge_code)
    atom = CodeStructureAtom(executor, parsers=_get_mock_parsers())

    t0 = time.time()
    result = atom.run({"intent": "skeletonize", "path": "test.py"})
    t1 = time.time()

    assert result.status == AtomStatus.SUCCESS
    assert (t1 - t0) < 1.0, "Skeletonize logic exceeded NFR-1 1.0s latency bound!"


def test_atom_get_supported_capabilities_aggregates_parsers() -> None:
    executor = MagicMock()

    mock_parser_1 = MagicMock()
    mock_parser_1.supported_intents.return_value = {"skeleton", "symbol"}
    mock_parser_1.supported_parameters.return_value = {"visibility"}

    mock_parser_2 = MagicMock()
    mock_parser_2.supported_intents.return_value = {"skeleton", "framework_markers"}
    mock_parser_2.supported_parameters.return_value = {"decorator_filter"}

    parsers = {
        (".py",): mock_parser_1,
        (".java",): mock_parser_2,
    }

    atom = CodeStructureAtom(executor, parsers=parsers)
    intents, params = atom.get_supported_capabilities()

    assert intents == {"skeleton", "symbol", "framework_markers"}
    assert params == {"visibility", "decorator_filter"}
