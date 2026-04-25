import pytest

from specweaver.workspace.parsers.cpp.codestructure import CppCodeStructure


@pytest.fixture
def parser() -> CppCodeStructure:
    return CppCodeStructure()


def test_extract_skeleton(parser: CppCodeStructure) -> None:
    code = """#include <iostream>
namespace MyLib {
    class Point {
    public:
        int x;
        int y;
        Point() { x = 0; y = 0; }
    };
    void print() { std::cout << "hello"; }
}
"""
    skeleton = parser.extract_skeleton(code)
    assert "class Point" in skeleton
    assert "void print" in skeleton
    assert "std::cout" not in skeleton


def test_extract_symbol(parser: CppCodeStructure) -> None:
    code = """class Point { public: int x; };"""
    symbol = parser.extract_symbol(code, "Point")
    assert "class Point" in symbol


def test_extract_symbol_body(parser: CppCodeStructure) -> None:
    code = """class Point { public: int x; };"""
    body = parser.extract_symbol_body(code, "Point")
    assert body.strip() == "{ public: int x; }"


def test_list_symbols(parser: CppCodeStructure) -> None:
    code = """
namespace Math {
    class Vector {};
    void multiply() {}
}
"""
    symbols = parser.list_symbols(code)
    assert set(symbols) == {"Math", "Vector", "multiply"}


def test_list_symbols_visibility(parser: CppCodeStructure) -> None:
    code = """
class Data {
public:
    void get_data() {}
private:
    void _internal() {}
};
"""
    # Visibility filtering should return only public symbols.
    # Note: Access specifiers apply to members, but the visibility param allows filtering them.
    # Actually, we might just filter methods inside access_specifier blocks.
    # Let's see if the implementation does that.
    symbols = parser.list_symbols(code, visibility=["public"])
    assert "get_data" in symbols
    assert "_internal" not in symbols


def test_list_symbols_decorator_filter_option_c(parser: CppCodeStructure) -> None:
    code = """
[[nodiscard]] int compute() { return 42; }
__attribute__((always_inline)) void fast() {}
void normal() {}
"""
    symbols = parser.list_symbols(code, decorator_filter="nodiscard")
    assert "compute" in symbols
    assert "fast" not in symbols
    assert "normal" not in symbols

    symbols_inline = parser.list_symbols(code, decorator_filter="always_inline")
    assert "fast" in symbols_inline
    assert "compute" not in symbols_inline


def test_extract_imports(parser: CppCodeStructure) -> None:
    code = """
#include <iostream>
#include "my_header.hpp"
int main() { return 0; }
"""
    imports = parser.extract_imports(code)
    assert set(imports) == {"#include <iostream>", '#include "my_header.hpp"'}


def test_extract_traceability_tags(parser: CppCodeStructure) -> None:
    code = """
// @trace(FR-1)
int main() { return 0; }
"""
    tags = parser.extract_traceability_tags(code)
    assert tags == {"FR-1"}


def test_replace_symbol_body(parser: CppCodeStructure) -> None:
    code = """void print() { std::cout << "old"; }"""
    new_code = parser.replace_symbol_body(code, "print", '{\n    std::cout << "new";\n}')
    assert "new" in new_code
    assert "old" not in new_code


def test_get_binary_ignore_patterns(parser: CppCodeStructure) -> None:
    patterns = parser.get_binary_ignore_patterns()
    assert "*.o" in patterns


def test_add_symbol(parser: CppCodeStructure) -> None:
    code = """
class Point {
public:
    int x;
};
"""
    new_code = parser.add_symbol(code, "Point", "int y;")
    assert "int y;" in new_code


def test_cpp_parser_default_directory_ignores(parser: CppCodeStructure) -> None:
    ignores = parser.get_default_directory_ignores()
    assert "build/" in ignores
    assert "obj/" in ignores


def test_cpp_parser_extracts_enum_body(parser: CppCodeStructure) -> None:
    code = "enum Color { RED, GREEN, BLUE };"
    body = parser.extract_symbol_body(code, "Color")
    assert body.strip() == "{ RED, GREEN, BLUE }"


def test_cpp_parser_visibility_deep_filter(parser: CppCodeStructure) -> None:
    code = """
class Core {
    int _secret;
public:
    void init() {}
protected:
    void setup() {}
};
"""
    public_symbols = parser.list_symbols(code, visibility=["public"])
    assert "init" in public_symbols
    assert "setup" not in public_symbols
    assert "_secret" not in public_symbols

    protected_symbols = parser.list_symbols(code, visibility=["protected"])
    assert "setup" in protected_symbols
    assert "init" not in protected_symbols


def test_cpp_parser_handles_unknown_attributes_gracefully(parser: CppCodeStructure) -> None:
    code = "[[unknown_attr]] void method() {}"
    # Should not crash, and should not return 'method' if looking for a different decorator
    symbols = parser.list_symbols(code, decorator_filter="nodiscard")
    assert len(symbols) == 0
    # Should find it if we look for the exact unknown_attr
    symbols2 = parser.list_symbols(code, decorator_filter="unknown_attr")
    assert "method" in symbols2
