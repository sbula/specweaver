import pytest

from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure


@pytest.fixture
def parser() -> JavaCodeStructure:
    return JavaCodeStructure()


def test_extract_traceability_tags_empty(parser: JavaCodeStructure) -> None:
    code = "void func() {}\n"
    assert parser.extract_traceability_tags(code) == set()


def test_extract_traceability_tags_single(parser: JavaCodeStructure) -> None:
    code = """
void test_some_behavior() {
    // @trace(FR-1)
    System.out.println(true);
}
"""
    assert parser.extract_traceability_tags(code) == {"FR-1"}


def test_extract_traceability_tags_multiple(parser: JavaCodeStructure) -> None:
    code = """
class TestFeature {
    // @trace(FR-1, FR-2)
    void test_one() {
        // @trace(NFR-1)
    }
}
"""
    assert parser.extract_traceability_tags(code) == {"FR-1", "FR-2", "NFR-1"}
