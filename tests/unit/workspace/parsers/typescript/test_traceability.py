import pytest

from specweaver.workspace.parsers.typescript.codestructure import TypeScriptCodeStructure


@pytest.fixture
def parser() -> TypeScriptCodeStructure:
    return TypeScriptCodeStructure()

def test_extract_traceability_tags_empty(parser: TypeScriptCodeStructure) -> None:
    code = "function func() {}\n"
    assert parser.extract_traceability_tags(code) == set()

def test_extract_traceability_tags_single(parser: TypeScriptCodeStructure) -> None:
    code = """
function test_some_behavior() {
    // @trace(FR-1)
    console.log(true);
}
"""
    assert parser.extract_traceability_tags(code) == {"FR-1"}

def test_extract_traceability_tags_multiple(parser: TypeScriptCodeStructure) -> None:
    code = """
class TestFeature {
    // @trace(FR-1, FR-2)
    test_one() {
        // @trace(NFR-1)
    }
}
"""
    assert parser.extract_traceability_tags(code) == {"FR-1", "FR-2", "NFR-1"}
