import pytest

from specweaver.workspace.parsers.rust.codestructure import RustCodeStructure


@pytest.fixture
def parser() -> RustCodeStructure:
    return RustCodeStructure()

def test_extract_traceability_tags_empty(parser: RustCodeStructure) -> None:
    code = "fn func() {}\n"
    assert parser.extract_traceability_tags(code) == set()

def test_extract_traceability_tags_single(parser: RustCodeStructure) -> None:
    code = """
fn test_some_behavior() {
    // @trace(FR-1)
    assert!(true);
}
"""
    assert parser.extract_traceability_tags(code) == {"FR-1"}

def test_extract_traceability_tags_multiple(parser: RustCodeStructure) -> None:
    code = """
struct TestFeature;
impl TestFeature {
    // @trace(FR-1, FR-2)
    fn test_one() {
        // @trace(NFR-1)
    }
}
"""
    assert parser.extract_traceability_tags(code) == {"FR-1", "FR-2", "NFR-1"}
