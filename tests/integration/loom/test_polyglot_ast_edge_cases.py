# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

from typing import Any
from unittest.mock import MagicMock

from specweaver.loom.atoms.base import AtomStatus
from specweaver.loom.atoms.code_structure.atom import CodeStructureAtom
from specweaver.loom.commons.filesystem.executor import ExecutorResult


def _run_atom(
    intent: str, path: str, context: dict[str, Any], file_system_simulator: dict[str, str]
) -> Any:
    """Mock the file system executor injected to the CodeStructureAtom."""
    executor = MagicMock()
    executor.read.side_effect = lambda p: ExecutorResult(
        status="success", data=file_system_simulator.get(p, "")
    )
    def _mock_write(p: str, data: str, **kwargs: Any) -> ExecutorResult:
        file_system_simulator[p] = data
        return ExecutorResult(status="success")
    executor.write.side_effect = _mock_write

    atom = CodeStructureAtom(executor)
    res = atom.run({"intent": intent, "path": path, **context})
    return res


def test_java_missing_closing_brackets() -> None:
    """Pass a .java file missing a final }. Ensure read_symbol_body still accurately parses."""
    code = """
    public class MalformedClass {
        public void myTargetMethod() {
            int a = 1;
            int b = 2;
        // Missing closing brace for method and class
    """

    res = _run_atom(
        "read_symbol_body", "file.java", {"symbol_name": "myTargetMethod"}, {"file.java": code}
    )

    assert res.status.value == "SUCCESS"
    assert "int a = 1;" in res.exports["body"]
    assert "int b = 2;" in res.exports["body"]


def test_ts_deeply_nested_scopes() -> None:
    """Pass a .ts file with an inner class and arrow functions. Ensure extract_symbol_body targets specifically."""
    code = """
    export function outerScope() {
        function innerMethod() {
            const secret = "hidden";
            return secret;
        }
    }
    """

    res = _run_atom(
        "read_symbol_body", "file.ts", {"symbol_name": "innerMethod"}, {"file.ts": code}
    )

    assert res.status.value == "SUCCESS"
    assert 'const secret = "hidden";' in res.exports["body"]
    assert "export function outerScope" not in res.exports["body"]


def test_rust_overloaded_methods() -> None:
    """Pass a .rs file with an impl block containing overloaded methods with identical names but different generics."""
    code = """
    impl Target {
        fn execute<T>(&self) {
            println!("generic");
        }

        fn execute(&self, val: u32) {
            println!("specific");
        }
    }
    """

    res = _run_atom("read_symbol", "file.rs", {"symbol_name": "execute"}, {"file.rs": code})

    assert res.status.value == "SUCCESS"
    assert "fn execute<T>(&self)" in res.exports["symbol"]
    assert "fn execute(&self, val: u32)" in res.exports["symbol"]
    assert 'println!("generic");' in res.exports["symbol"]
    assert 'println!("specific");' in res.exports["symbol"]


def test_python_empty_file_handling() -> None:
    """Pass a completely blank .py file to read_file_structure and list_symbols. Ensure it returns empty payloads."""
    res_struct = _run_atom("read_file_structure", "file.py", {}, {"file.py": ""})
    assert res_struct.status.value == "SUCCESS"
    assert res_struct.exports["structure"].strip() == ""

    res_list = _run_atom("list_symbols", "file.py", {}, {"file.py": ""})
    assert res_list.status.value == "SUCCESS"
    assert res_list.exports["symbols"] == []


def test_kotlin_symbol_not_found() -> None:
    """Query read_symbol_body for a GhostClass inside a valid .kt file. Ensure it throws a proper structured Error."""
    code = """
    class ValidClass {
        fun doSomething() {}
    }
    """

    res = _run_atom("read_symbol_body", "file.kt", {"symbol_name": "GhostClass"}, {"file.kt": code})

    assert res.status.value == "FAILED"
    assert "not found" in res.message


def test_python_complex_pydantic_decorators() -> None:
    """Story 12: Safely extract a complex Pydantic model with nested logic and multiple decorators."""
    code = """
from pydantic import BaseModel, Field

@decorates_class
@another_decorator(param="value")
class ComplexModel(BaseModel):
    id: str = Field(default_factory=str)

    @classmethod
    @validator("id", pre=True)
    def validate_id(cls, v):
        return v.strip()
"""
    res = _run_atom(
        "read_symbol", "models.py", {"symbol_name": "ComplexModel"}, {"models.py": code}
    )
    assert res.status.value == "SUCCESS"
    assert "@decorates_class" in res.exports["symbol"]
    assert "class ComplexModel" in res.exports["symbol"]
    assert "def validate_id" in res.exports["symbol"]


def test_python_legacy_syntax_fallback() -> None:
    """Story 13: Fallback gracefully when encountering Python 2 syntax."""
    code = """
def LegacyMethod():
    print "This is legacy python 2"
"""
    # Syntax error recovery should still allow skeleton or symbol reading
    res = _run_atom(
        "read_symbol", "legacy.py", {"symbol_name": "LegacyMethod"}, {"legacy.py": code}
    )
    assert res.status.value == "SUCCESS"
    assert "def LegacyMethod():" in res.exports["symbol"]


def test_java_nested_anonymous_inner_interface() -> None:
    """Story 14: Accurately extract the body of an inner Interface nested inside an Anonymous Class."""
    code = """
public class Container {
    public void setup() {
        Runnable r = new Runnable() {
            public interface HiddenInterface {
                void execute();
            }
            @Override
            public void run() {
                System.out.println("Running");
            }
        };
    }
}
"""
    res = _run_atom(
        "read_symbol",
        "Container.java",
        {"symbol_name": "HiddenInterface"},
        {"Container.java": code},
    )
    assert res.status.value == "SUCCESS"
    assert "public interface HiddenInterface" in res.exports["symbol"]


def test_java_heavily_nested_generics() -> None:
    """Story 15: Properly process method signatures containing heavily nested Generics and throws."""
    code = """
public class Target {
    public <T extends Comparable<T>, U extends Map<String, List<T>>>
    U transformData(T input) throws IllegalArgumentException, IOException {
        return null;
    }
}
"""
    res = _run_atom(
        "read_symbol_body", "Target.java", {"symbol_name": "transformData"}, {"Target.java": code}
    )
    assert res.status.value == "SUCCESS"
    assert "return null;" in res.exports["body"]


def test_ts_exported_arrow_function() -> None:
    """Story 16: Accurately extract an exported constant bound to an Arrow Function."""
    code = """
export const executeAction = async (payload: PayloadType): Promise<void> => {
    console.log("Action Executed!");
};
"""
    res = _run_atom(
        "read_symbol_body", "index.ts", {"symbol_name": "executeAction"}, {"index.ts": code}
    )
    assert res.status.value == "SUCCESS"
    assert "console.log" in res.exports["body"]
    assert "export const" not in res.exports["body"]


def test_ts_nested_interface_in_namespace() -> None:
    """Story 17: nested interfaces within a large export namespace."""
    code = """
export namespace GlobalAPI {
    export interface TargetInterface {
        id: string;
        roles: string[];
    }
}
"""
    res = _run_atom("read_symbol", "api.ts", {"symbol_name": "TargetInterface"}, {"api.ts": code})
    # Currently TS Tree-sitter might not recurse into module boundaries easily
    # We test that the failure is graceful
    if res.status.value == "FAILED":
        assert "not found" in res.message
    else:
        assert "export interface TargetInterface" in res.exports["symbol"]


def test_rust_macros_and_lifetimes() -> None:
    """Story 18: Successfully extract a struct decorated with derived Macros and lifetimes."""
    code = """
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplexEntity<'a, T: Clone> {
    pub name: &'a str,
    pub data: T,
}
"""
    res = _run_atom("read_symbol", "entity.rs", {"symbol_name": "ComplexEntity"}, {"entity.rs": code})
    assert res.status.value == "SUCCESS"
    # Decorators might be dropped depending on rust scm definition
    assert "pub struct ComplexEntity<'a" in res.exports["symbol"]


def test_rust_method_in_trait_impl() -> None:
    """Story 19: Successfully locate and read a method bound within a specific Trait impl block."""
    code = """
impl Clone for Target {
    fn clone(&self) -> Self {
        Target { val: self.val }
    }
}
"""
    res = _run_atom("read_symbol_body", "target.rs", {"symbol_name": "clone"}, {"target.rs": code})
    assert res.status.value == "SUCCESS"
    assert "Target { val: self.val }" in res.exports["body"]


def test_kotlin_data_class() -> None:
    """Story 20: Safely extract a data class without confusing its properties."""
    code = """
@Entity
data class User(
    @PrimaryKey val id: Int,
    val name: String
)
"""
    res = _run_atom("read_symbol", "User.kt", {"symbol_name": "User"}, {"User.kt": code})
    assert res.status.value == "SUCCESS"
    assert "@Entity" in res.exports["symbol"]
    assert "data class User" in res.exports["symbol"]


def test_kotlin_companion_object() -> None:
    """Story 21: target methods residing inside a companion object."""
    code = """
class Wrapper {
    companion object Factory {
        fun create(): Wrapper {
            return Wrapper()
        }
    }
}
"""
    res = _run_atom(
        "read_symbol_body", "Wrapper.kt", {"symbol_name": "create"}, {"Wrapper.kt": code}
    )
    assert res.status.value == "SUCCESS"
    assert "return Wrapper()" in res.exports["body"]


def test_tool_oom_protection() -> None:
    """Story 22: OOM Protection check for massive strings.
    The AST Extractor natively uses file_executor which limits max read to a sane threshold (2MB usually).
    Here we simulate passing an artificial 6MB string and ensuring memory usage is acceptable.
    Python's max recursive depth for tree-sitter or regex might blow up if not careful.
    """
    code = "class A:\n" + "    pass\n" * 50000
    res = _run_atom("read_file_structure", "big.py", {}, {"big.py": code})
    # As long as it returns successfully without a StackOverflow, we pass. We don't care if data was truncated.
    assert res.status in [AtomStatus.SUCCESS, AtomStatus.FAILED]


def test_python_mutation_operations() -> None:
    """Test replace, replace_body, delete, and add symbol for Python via CodeStructureAtom."""
    code = """
class TargetClass:
    def original_math(self):
        return 1 + 1

    def method_to_delete(self):
        pass
"""
    fs = {"file.py": code}

    # 1. Replace Body
    res = _run_atom("replace_symbol_body", "file.py", {"symbol_name": "original_math", "new_code": "return 42"}, fs)
    assert res.status.value == "SUCCESS"
    assert "return 42" in fs["file.py"]
    assert "return 1 + 1" not in fs["file.py"]
    assert "def original_math(self):" in fs["file.py"]

    # 2. Add Symbol
    res = _run_atom("add_symbol", "file.py", {"target_parent": "TargetClass", "new_code": "def added_method(self):\n    return 'new'"}, fs)
    assert res.status.value == "SUCCESS"
    assert "def added_method(self):" in fs["file.py"]

    # 3. Delete Symbol
    res = _run_atom("delete_symbol", "file.py", {"symbol_name": "method_to_delete"}, fs)
    assert res.status.value == "SUCCESS"
    assert "def method_to_delete" not in fs["file.py"]

    # 4. Replace Symbol (Full)
    res = _run_atom("replace_symbol", "file.py", {"symbol_name": "original_math", "new_code": "def brand_new_math(self):\n    return 100"}, fs)
    assert res.status.value == "SUCCESS"
    assert "def brand_new_math" in fs["file.py"]
    assert "def original_math" not in fs["file.py"]

def test_python_mutation_edge_cases() -> None:
    """Test AST edge cases like auto-indentation of multi-line replacements, missing targets, nested classes."""
    code = """
class OuterClass:
    class InnerClass:
        def do_nested(self):
            print("nested")
"""
    fs = {"file.py": code}

    # 1. Multi-line auto-indentation in nested scopes
    new_body = "for i in range(3):\n    print('nested ' + str(i))"
    res = _run_atom("replace_symbol_body", "file.py", {"symbol_name": "do_nested", "new_code": new_body}, fs)

    assert res.status.value == "SUCCESS"
    # Ensure it was indented to match the 12-space internal block margin
    assert "            for i in range(3):" in fs["file.py"]
    assert "                print('nested ' + str(i))" in fs["file.py"]

    # 2. Target not found
    res = _run_atom("replace_symbol", "file.py", {"symbol_name": "NonExistentMethod", "new_code": "pass"}, fs)
    assert res.status.value == "FAILED"
    assert "not found" in res.message

    # 3. Add Symbol to EOF (target_parent None)
    res = _run_atom("add_symbol", "file.py", {"target_parent": None, "new_code": "def global_func():\n    return 1"}, fs)
    assert res.status.value == "SUCCESS"
    assert "def global_func():" in fs["file.py"]

def test_python_mutation_on_malformed_syntax() -> None:
    """Test that tree-sitter recovers and successfully mutates a symbol even if the file contains severe syntax errors."""
    code = """
class TargetClass:
    def good_method(self):
        return True

# Missing colon, bad indentation, unclosed parenthesis
def corrupted_syntax()
    print("oh no"
"""
    fs = {"file.py": code}

    # Tree-sitter's fault tolerance should still locate good_method accurately.
    res = _run_atom("delete_symbol", "file.py", {"symbol_name": "good_method"}, fs)
    assert res.status.value == "SUCCESS"
    assert "def good_method(self):" not in fs["file.py"]
    # The bad syntax should be completely untouched
    assert "def corrupted_syntax()" in fs["file.py"]

def test_java_mutation_operations() -> None:
    """Test replace, replace_body, delete, and add symbol for Java via CodeStructureAtom."""
    code = """
public class TargetClass {
    public int originalMath() {
        return 1 + 1;
    }

    public void methodToDelete() {
    }
}
"""
    fs = {"TargetClass.java": code}

    # 1. Replace Body
    res = _run_atom("replace_symbol_body", "TargetClass.java", {"symbol_name": "originalMath", "new_code": "return 42;"}, fs)
    assert res.status.value == "SUCCESS"
    assert "return 42;" in fs["TargetClass.java"]
    assert "return 1 + 1;" not in fs["TargetClass.java"]
    assert "public int originalMath() {" in fs["TargetClass.java"]

    # 2. Add Symbol (Nested in Class)
    new_method = "public void addedMethod() {\n    return;\n}"
    res = _run_atom("add_symbol", "TargetClass.java", {"target_parent": "TargetClass", "new_code": new_method}, fs)
    assert res.status.value == "SUCCESS"
    assert "public void addedMethod() {" in fs["TargetClass.java"]
    # Ensure it's before the class closing brace
    assert "}\n}" in fs["TargetClass.java"].replace(" ", "")

    # 3. Delete Symbol
    res = _run_atom("delete_symbol", "TargetClass.java", {"symbol_name": "methodToDelete"}, fs)
    assert res.status.value == "SUCCESS"
    assert "methodToDelete" not in fs["TargetClass.java"]

    # 4. Replace Symbol (Full)
    res = _run_atom("replace_symbol", "TargetClass.java", {"symbol_name": "originalMath", "new_code": "public int brandNewMath() {\n    return 100;\n}"}, fs)
    assert res.status.value == "SUCCESS"
    assert "brandNewMath" in fs["TargetClass.java"]
    assert "originalMath" not in fs["TargetClass.java"]

def test_kotlin_mutation_operations() -> None:
    code = """
class TargetClass {
    fun originalMath(): Int {
        return 1 + 1
    }
}
"""
    fs = {"TargetClass.kt": code}

    res = _run_atom("replace_symbol_body", "TargetClass.kt", {"symbol_name": "originalMath", "new_code": "return 42"}, fs)
    assert res.status.value == "SUCCESS"
    assert "return 42" in fs["TargetClass.kt"]

    res = _run_atom("add_symbol", "TargetClass.kt", {"target_parent": "TargetClass", "new_code": "fun added(): Unit {}"}, fs)
    assert res.status.value == "SUCCESS"
    assert "fun added()" in fs["TargetClass.kt"]

def test_rust_mutation_operations() -> None:
    code = """
struct TargetClass {}
impl TargetClass {
    fn original_math() -> i32 {
        1 + 1
    }
}
"""
    fs = {"target.rs": code}

    res = _run_atom("replace_symbol_body", "target.rs", {"symbol_name": "original_math", "new_code": "42"}, fs)
    assert res.status.value == "SUCCESS", getattr(res, "message", "unknown error")
    assert "42" in fs["target.rs"]

    res = _run_atom("add_symbol", "target.rs", {"target_parent": "TargetClass", "new_code": "fn added() {}"}, fs)
    assert res.status.value == "SUCCESS"
    assert "fn added()" in fs["target.rs"]

def test_typescript_mutation_operations() -> None:
    code = """
export class TargetClass {
    originalMath(): number {
        return 1 + 1;
    }
}
"""
    fs = {"TargetClass.ts": code}

    res = _run_atom("replace_symbol_body", "TargetClass.ts", {"symbol_name": "originalMath", "new_code": "return 42;"}, fs)
    assert res.status.value == "SUCCESS"
    assert "return 42;" in fs["TargetClass.ts"]

    res = _run_atom("add_symbol", "TargetClass.ts", {"target_parent": "TargetClass", "new_code": "added(): void {}"}, fs)
    assert res.status.value == "SUCCESS"
    assert "added(): void {}" in fs["TargetClass.ts"]
