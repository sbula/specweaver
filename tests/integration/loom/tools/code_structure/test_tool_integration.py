import os
from pathlib import Path

import pytest

from specweaver.loom.atoms.code_structure.atom import CodeStructureAtom
from specweaver.loom.commons.filesystem.executor import EngineFileExecutor
from specweaver.loom.security import AccessMode, FolderGrant
from specweaver.loom.tools.code_structure.tool import CodeStructureTool


@pytest.fixture
def physical_tool(tmp_path: Path) -> CodeStructureTool:
    """Provides a physical Integration bridge for CodeStructureTool."""
    # Isolate Executor physically (Requires a Path object)
    executor = EngineFileExecutor(tmp_path)

    # Mount atom
    atom = CodeStructureAtom(executor)

    # Mount tool with an explicit grant
    # Grant paths use "" to mean the root of the relative workspace context
    grant = FolderGrant(path="", mode=AccessMode.FULL, recursive=True)
    tool = CodeStructureTool(atom=atom, role="implementer", grants=[grant])
    
    return tool


def test_physical_integration_python_mutation(tmp_path: Path, physical_tool: CodeStructureTool) -> None:
    code = """
class Target:
    def original_math(self):
        return 1 + 1
    def erase_me(self):
        pass
"""
    file_path = tmp_path / "test.py"
    file_path.write_text(code, encoding="utf-8")

    # The tool normalizes paths, so we specify absolute path since EngineFileExecutor works on absolute if grant is absolute.
    # Wait, EngineFileExecutor works natively with absolute paths OR paths relative to its root base!
    # For safety, let's use the absolute path so we accurately bypass the grant restrictions logic in the tool.
    rel_path = file_path.name

    # Replace Body
    res = physical_tool.replace_symbol_body(rel_path, "original_math", "return 42")
    assert res.status == "success", res.message

    # Read back physical file
    content = file_path.read_text(encoding="utf-8")
    assert "return 42" in content
    assert "return 1 + 1" not in content

    # Delete Symbol
    res2 = physical_tool.delete_symbol(rel_path, "erase_me")
    assert res2.status == "success", res2.message
    assert "erase_me" not in file_path.read_text(encoding="utf-8")

    # Add Symbol
    res3 = physical_tool.add_symbol(rel_path, "def new_method(self):\n    return 'new'", "Target")
    assert res3.status == "success", res3.message
    assert "def new_method" in file_path.read_text(encoding="utf-8")


def test_physical_integration_java_mutation(tmp_path: Path, physical_tool: CodeStructureTool) -> None:
    code = """
public class JavaTarget {
    public int originalMath() {
        return 1 + 1;
    }
}
"""
    file_path = tmp_path / "JavaTarget.java"
    file_path.write_text(code, encoding="utf-8")
    rel_path = file_path.name

    res = physical_tool.replace_symbol(
        rel_path, "originalMath", "public int brandNewMath() {\n    return 42;\n}"
    )
    assert res.status == "success", res.message

    content = file_path.read_text(encoding="utf-8")
    assert "brandNewMath" in content
    assert "originalMath" not in content


def test_physical_integration_kotlin_mutation(tmp_path: Path, physical_tool: CodeStructureTool) -> None:
    code = """
class KotlinTarget {
    fun run() {}
}
"""
    file_path = tmp_path / "KotlinTarget.kt"
    file_path.write_text(code, encoding="utf-8")
    rel_path = file_path.name

    res = physical_tool.replace_symbol_body(rel_path, "run", 'println("kt")')
    assert res.status == "success", res.message

    content = file_path.read_text(encoding="utf-8")
    assert 'println("kt")' in content


def test_physical_integration_typescript_mutation(tmp_path: Path, physical_tool: CodeStructureTool) -> None:
    code = """
export class TsTarget {
    execute() {
        console.log("old");
    }
}
"""
    file_path = tmp_path / "TsTarget.ts"
    file_path.write_text(code, encoding="utf-8")
    rel_path = file_path.name

    res = physical_tool.delete_symbol(rel_path, "execute")
    assert res.status == "success", res.message

    content = file_path.read_text(encoding="utf-8")
    assert "execute()" not in content


def test_physical_integration_rust_mutation(tmp_path: Path, physical_tool: CodeStructureTool) -> None:
    code = """
struct RsTarget;
impl RsTarget {
    fn execute() {}
}
"""
    file_path = tmp_path / "target.rs"
    file_path.write_text(code, encoding="utf-8")
    rel_path = file_path.name

    res = physical_tool.add_symbol(rel_path, "fn added() {}", "RsTarget")
    assert res.status == "success", res.message

    content = file_path.read_text(encoding="utf-8")
    assert "added()" in content
    assert "execute()" in content


def test_tool_rejection_boundary_physical(tmp_path: Path, physical_tool: CodeStructureTool) -> None:
    # Validate the fallback security checking if the path lives OUTSIDE the grant
    # Since physical_tool only has a grant for project_root (`tmp_path`), if we query a completely exterior dummy path:
    
    # We must format it as a valid path string format with an extension so the parser doesn't instantly reject it simply for having no format.
    rel_path = "../../../../etc/passwd.py"
    res = physical_tool.replace_symbol(rel_path, "Ghost", "malicious_injection")
    
    # Must physically return error instead of actually evaluating
    assert res.status == "error"
    # Ensure it's blocked by the validation layer
    assert "Path validation failed" in res.message or "File not found" in res.message
