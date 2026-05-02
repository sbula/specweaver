import pytest

from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.ast.parsers.interfaces import CodeStructureError


@pytest.fixture
def parser() -> CCodeStructure:
    return CCodeStructure()


def test_extract_skeleton(parser: CCodeStructure) -> None:
    code = """#include <stdio.h>
int main() {
    printf("hello");
    return 0;
}
struct Point {
    int x;
    int y;
};
"""
    skeleton = parser.extract_skeleton(code)
    assert "#include <stdio.h>" in skeleton
    assert "int main" in skeleton
    assert "struct Point" in skeleton
    assert "printf" not in skeleton


def test_extract_symbol(parser: CCodeStructure) -> None:
    code = """int add(int a, int b) { return a + b; }"""
    symbol = parser.extract_symbol(code, "add")
    assert symbol == "int add(int a, int b) { return a + b; }"


def test_extract_symbol_body(parser: CCodeStructure) -> None:
    code = """int add(int a, int b) { return a + b; }"""
    body = parser.extract_symbol_body(code, "add")
    assert body.strip() == "{ return a + b; }"


def test_list_symbols(parser: CCodeStructure) -> None:
    code = """
int add(int a, int b) { return a + b; }
struct Point { int x; int y; };
"""
    symbols = parser.list_symbols(code)
    assert set(symbols) == {"add", "Point"}


def test_extract_imports(parser: CCodeStructure) -> None:
    code = """
#include <stdio.h>
#include "my_header.h"
int main() { return 0; }
"""
    imports = parser.extract_imports(code)
    assert set(imports) == {"#include <stdio.h>", '#include "my_header.h"'}


def test_extract_traceability_tags(parser: CCodeStructure) -> None:
    code = """
// @trace(FR-1)
int main() { return 0; }
/* @trace(FR-2, NFR-1) */
"""
    tags = parser.extract_traceability_tags(code)
    assert tags == {"FR-1", "FR-2", "NFR-1"}


def test_replace_symbol_body(parser: CCodeStructure) -> None:
    code = """int add(int a, int b) { return a + b; }"""
    new_code = parser.replace_symbol_body(code, "add", "{\n    return a - b;\n}")
    assert "return a - b;" in new_code
    assert "int add(int a, int b)" in new_code


def test_get_binary_ignore_patterns(parser: CCodeStructure) -> None:
    patterns = parser.get_binary_ignore_patterns()
    assert "*.o" in patterns
    assert "*.so" in patterns


def test_add_symbol(parser: CCodeStructure) -> None:
    code = """
struct Point {
    int x;
};
"""
    new_code = parser.add_symbol(code, "Point", "int y;")
    assert "int y;" in new_code
    assert "int x;" in new_code


def test_c_parser_raises_on_decorator_filter(parser: CCodeStructure) -> None:
    code = "int compute() { return 0; }"
    with pytest.raises(CodeStructureError, match="Decorator filtering is not supported"):
        parser.list_symbols(code, decorator_filter="inline")


def test_c_parser_visibility_returns_empty(parser: CCodeStructure) -> None:
    code = "int compute() { return 0; }"
    symbols = parser.list_symbols(code, visibility=["public"])
    assert len(symbols) == 0


def test_c_parser_default_directory_ignores(parser: CCodeStructure) -> None:
    ignores = parser.get_default_directory_ignores()
    assert "build/" in ignores
    assert "obj/" in ignores


def test_c_parser_extracts_struct_body(parser: CCodeStructure) -> None:
    code = "struct Data { int id; };"
    body = parser.extract_symbol_body(code, "Data")
    assert body.strip() == "{ int id; }"
