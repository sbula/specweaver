import pytest

from specweaver.workspace.parsers.kotlin.codestructure import KotlinCodeStructure


@pytest.fixture
def parser() -> KotlinCodeStructure:
    return KotlinCodeStructure()


def test_extract_traceability_tags_empty(parser: KotlinCodeStructure) -> None:
    code = "fun func() {}\n"
    assert parser.extract_traceability_tags(code) == set()


def test_extract_traceability_tags_single(parser: KotlinCodeStructure) -> None:
    code = """
fun test_some_behavior() {
    // @trace(FR-1)
    println(true)
}
"""
    assert parser.extract_traceability_tags(code) == {"FR-1"}


def test_extract_traceability_tags_multiple(parser: KotlinCodeStructure) -> None:
    code = """
class TestFeature {
    // @trace(FR-1, FR-2)
    fun test_one() {
        // @trace(NFR-1)
    }
}
"""
    assert parser.extract_traceability_tags(code) == {"FR-1", "FR-2", "NFR-1"}
