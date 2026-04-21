import pytest

from specweaver.workspace.parsers.python.codestructure import PythonCodeStructure


@pytest.fixture
def parser() -> PythonCodeStructure:
    return PythonCodeStructure()


def test_extract_traceability_tags_empty(parser: PythonCodeStructure) -> None:
    code = "def func(): pass\n"
    assert parser.extract_traceability_tags(code) == set()


def test_extract_traceability_tags_single(parser: PythonCodeStructure) -> None:
    code = """
def test_some_behavior():
    # @trace(FR-1)
    assert True
"""
    assert parser.extract_traceability_tags(code) == {"FR-1"}


def test_extract_traceability_tags_multiple(parser: PythonCodeStructure) -> None:
    code = """
class TestFeature:
    # @trace(FR-1, FR-2)
    def test_one(self):
        # @trace(NFR-1)
        pass
"""
    assert parser.extract_traceability_tags(code) == {"FR-1", "FR-2", "NFR-1"}


def test_extract_traceability_tags_different_spacing(parser: PythonCodeStructure) -> None:
    code = """
#@trace(FR-1)
# @trace( FR-2 )
#    @trace(FR-3)
"""
    assert parser.extract_traceability_tags(code) == {"FR-1", "FR-2", "FR-3"}
