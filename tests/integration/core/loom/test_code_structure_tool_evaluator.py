# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import pytest

from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom
from specweaver.core.loom.commons.filesystem.executor import FileExecutor
from specweaver.core.loom.security import AccessMode, FolderGrant
from specweaver.core.loom.tools.code_structure.tool import CodeStructureTool, CodeStructureToolError


@pytest.fixture
def mock_schemas():
    return {
        "fastapi": {
            "metadata": {"supported_languages": ["python"]},
            "decorators": {
                "dataclass": "Python standard library dataclass generator."
            }
        }
    }

def test_code_structure_atom_read_unrolled_symbol(tmp_path, mock_schemas):
    test_file = tmp_path / "test.py"
    test_file.write_text("@dataclass\nclass User:\n    id: int\n")

    executor = FileExecutor(cwd=tmp_path)
    atom = CodeStructureAtom(file_executor=executor, evaluator_schemas=mock_schemas, active_archetype="fastapi")

    context = {
        "intent": "read_unrolled_symbol",
        "path": "test.py",
        "symbol_name": "User"
    }

    result = atom.run(context)

    assert result.status.value == "SUCCESS", result.message
    assert "# [Framework Eval] Python standard library dataclass generator." in result.exports["symbol"]
    assert "class User:" in result.exports["symbol"]

def test_code_structure_tool_exposes_read_unrolled_symbol(tmp_path, mock_schemas):
    test_file = tmp_path / "test.py"
    test_file.write_text("@dataclass\nclass User:\n    id: int\n")

    executor = FileExecutor(cwd=tmp_path)
    atom = CodeStructureAtom(file_executor=executor, evaluator_schemas=mock_schemas, active_archetype="fastapi")

    tool = CodeStructureTool(atom=atom, role="implementer", grants=[FolderGrant(path="", mode=AccessMode.FULL, recursive=True)])

    assert hasattr(tool, "read_unrolled_symbol")

    res = tool.read_unrolled_symbol("test.py", "User")
    assert res.status == "success", res.message

def test_atom_graceful_unknown_extension_and_bare_symbol(tmp_path, mock_schemas):
    # Story 2 and 6
    # Use .xyz to ensure the atom rejects gracefully with FAILED instead of a hard crash
    test_file = tmp_path / "test.xyz"
    test_file.write_text("@dataclass\nclass User:\n    id: int\n")
    executor = FileExecutor(cwd=tmp_path)
    atom = CodeStructureAtom(file_executor=executor, evaluator_schemas=mock_schemas, active_archetype="fastapi")
    res = atom.run({"intent": "read_unrolled_symbol", "path": "test.xyz", "symbol_name": "User"})
    assert res.status.value == "FAILED"
    assert "not supported" in res.message.lower()

    # Story 6: supported extension (.py) but unrecognizable dict mapping (fallback to bare symbol)
    test_file2 = tmp_path / "test2.py"
    test_file2.write_text("@unknown\nclass User:\n    id: int\n")
    res2 = atom.run({"intent": "read_unrolled_symbol", "path": "test2.py", "symbol_name": "User"})
    assert res2.status.value == "SUCCESS"
    assert "[Framework Eval]" not in res2.exports["symbol"]
    assert "class User:" in res2.exports["symbol"]

def test_atom_evaluator_comment_routing_by_extension(tmp_path):
    # Story 7
    schemas = {
        "spring-boot": {
            "metadata": {"supported_languages": ["java", "kotlin"]},
            "decorators": {"Entity": "JPA Entity"}
        },
        "fastapi": {
            "metadata": {"supported_languages": ["python"]},
            "decorators": {"dataclass": "Python standard library dataclass generator."}
        }
    }
    fjava = tmp_path / "test.java"
    fjava.write_text("@Entity\nclass User {}\n")
    fpy = tmp_path / "test.py"
    fpy.write_text("@dataclass\nclass User:\n    id: int\n")

    executor = FileExecutor(cwd=tmp_path)
    # Evaluate specifically as spring-boot
    atom_java = CodeStructureAtom(file_executor=executor, evaluator_schemas=schemas, active_archetype="spring-boot")
    res_j = atom_java.run({"intent": "read_unrolled_symbol", "path": "test.java", "symbol_name": "User"})
    assert res_j.status.value == "SUCCESS"
    assert "// [Framework Eval] JPA Entity" in res_j.exports["symbol"]

    # Evaluate specifically as fastapi
    atom_py = CodeStructureAtom(file_executor=executor, evaluator_schemas=schemas, active_archetype="fastapi")
    res_p = atom_py.run({"intent": "read_unrolled_symbol", "path": "test.py", "symbol_name": "User"})
    assert res_p.status.value == "SUCCESS"
    assert "# [Framework Eval] Python standard library dataclass generator." in res_p.exports["symbol"]

def test_atom_cyclic_recursion_engine_safety(tmp_path):
    # Story 8
    schemas = {"fastapi": {"metadata": {"supported_languages": ["python"]}, "decorators": {"SelfReferencing": ">>{SelfReferencing}<<"}}}
    fpy = tmp_path / "test.py"
    fpy.write_text("@SelfReferencing\nclass User:\n    id: int\n")
    executor = FileExecutor(cwd=tmp_path)
    atom = CodeStructureAtom(file_executor=executor, evaluator_schemas=schemas, active_archetype="fastapi")
    res = atom.run({"intent": "read_unrolled_symbol", "path": "test.py", "symbol_name": "User"})

    # The atom should catch parsing errors or at least bubble up correctly as FAILED?
    # Wait, if EvaluatorDepthError is raised, does Atom catch it?
    # The Atom base class generally wraps executor runs, but in _handle_read_symbol it doesn't currently catch it,
    # let's assert it gracefully returns AtomStatus.FAILED. If it crashes, we'll fix the code!
    assert res.status.value == "FAILED"
    assert "cyclic" in res.message.lower() or "depth" in res.message.lower()

def test_atom_graceful_missing_symbol(tmp_path, mock_schemas):
    # Story 9
    test_file = tmp_path / "test.py"
    test_file.write_text("@dataclass\nclass User:\n    id: int\n")
    executor = FileExecutor(cwd=tmp_path)
    atom = CodeStructureAtom(file_executor=executor, evaluator_schemas=mock_schemas, active_archetype="fastapi")
    res = atom.run({"intent": "read_unrolled_symbol", "path": "test.py", "symbol_name": "Database"})
    assert res.status.value == "FAILED"
    assert "not found" in res.message.lower()

def test_tool_blocks_role_without_intent(tmp_path, mock_schemas):
    # Story 3
    test_file = tmp_path / "test.py"
    test_file.write_text("class User:\n    id: int\n")
    executor = FileExecutor(cwd=tmp_path)
    atom = CodeStructureAtom(file_executor=executor, evaluator_schemas=mock_schemas, active_archetype="fastapi")

    # Reviewer and Implementer have read_unrolled_symbol, but let's say "drafter" does not
    tool = CodeStructureTool(atom=atom, role="drafter", grants=[FolderGrant(path="", mode=AccessMode.FULL, recursive=True)])
    with pytest.raises(CodeStructureToolError, match="not allowed for role"):
        tool.read_unrolled_symbol("test.py", "User")

def test_tool_blocks_invalid_folder_grant(tmp_path, mock_schemas):
    # Story 4
    test_file = tmp_path / "test.py"
    test_file.write_text("class User:\n    id: int\n")
    executor = FileExecutor(cwd=tmp_path)
    atom = CodeStructureAtom(file_executor=executor, evaluator_schemas=mock_schemas, active_archetype="fastapi")

    # Grant ONLY to src/ folder, but we try to access test.py
    tool = CodeStructureTool(atom=atom, role="implementer", grants=[FolderGrant(path="src", mode=AccessMode.FULL, recursive=True)])
    res = tool.read_unrolled_symbol("test.py", "User")
    assert res.status == "error"
    assert "no grant covers path" in res.message.lower()

# ---------------------------------------------------------------------------
# Feature 3.30a: Dynamic Plugin Composition & Testing
# ---------------------------------------------------------------------------

def test_tool_dispatcher_intent_hide_with_plugins(tmp_path):
    """Integration Story 4: Dispatcher pipeline filters JSON schema properly."""
    from specweaver.core.loom.dispatcher import ToolDispatcher
    from specweaver.core.loom.security import WorkspaceBoundary

    context = tmp_path / "context.yaml"
    context.write_text("archetype: generic\nplugins: [security, broken, malformed]")

    evaluators = tmp_path / ".specweaver" / "evaluators"
    evaluators.mkdir(parents=True, exist_ok=True)
    # generic doesn't hide list_symbols, but security does. broken evaluates to None internally.
    (evaluators / "generic.yaml").write_text("intents:\n  hide: [read_unrolled_symbol]")
    (evaluators / "security.yaml").write_text("intents:\n  hide: [list_symbols]")
    (evaluators / "broken.yaml").write_text("intents: null")
    (evaluators / "malformed.yaml").write_text("intents:\n  hide: fake_scalar")


    boundary = WorkspaceBoundary(roots=[tmp_path])
    dispatcher = ToolDispatcher.create_standard_set(boundary, role="implementer", allowed_tools=["ast"])

    tool_names = [t.name for t in dispatcher.available_tools()]

    # Check that BOTH generic (read_unrolled_symbol) and security (list_symbols) are hidden
    # "anyOf" or "oneOf" list under intents should NOT contain them
    assert "read_unrolled_symbol" not in tool_names
    assert "list_symbols" not in tool_names
    # Standard tools like read_file_structure should still be there conceptually
    assert "read_file_structure" in tool_names    # (or whatever is native, but just verify the hidden ones are stripped)

def test_code_structure_atom_unroll_with_plugin(tmp_path):
    """Integration Story (New): Atom unrolls decorators across base and plugin schemas."""
    schemas = {
        "spring-boot": {
            "metadata": {"supported_languages": ["java"]},
            "decorators": {"Entity": "JPA Entity"}
        },
        "spring-security": {
            "metadata": {"supported_languages": ["java"]},
            "decorators": {"PreAuthorize": "Security Boundary"}
        }
    }

    test_file = tmp_path / "test.java"
    test_file.write_text("@Entity\n@PreAuthorize\nclass User {}\n")

    executor = FileExecutor(cwd=tmp_path)
    atom = CodeStructureAtom(file_executor=executor, evaluator_schemas=schemas, active_archetype="spring-boot", plugins=["spring-security"])

    res = atom.run({"intent": "read_unrolled_symbol", "path": "test.java", "symbol_name": "User"})
    assert res.status.value == "SUCCESS"
    assert "// [Framework Eval] JPA Entity" in res.exports["symbol"]
    assert "// [Framework Eval] Security Boundary" in res.exports["symbol"]

def test_code_structure_atom_list_symbols_decorator_filter(tmp_path):
    """Integration Story: Tool Evaluator securely passes decorator_filter to Atom."""
    test_file = tmp_path / "Controller.java"
    test_file.write_text("""
@RestController
class UserController {}

class NormalClass {}

@RestController
class AuthController {}
""")

    executor = FileExecutor(cwd=tmp_path)
    atom = CodeStructureAtom(file_executor=executor, evaluator_schemas={}, active_archetype="base")

    res = atom.run({
        "intent": "list_symbols",
        "path": "Controller.java",
        "decorator_filter": "RestController"
    })

    assert res.status.value == "SUCCESS"

    symbols = res.exports["symbols"]
    assert "UserController" in symbols
    assert "AuthController" in symbols
    assert "NormalClass" not in symbols

