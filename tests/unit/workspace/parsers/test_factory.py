from specweaver.workspace.parsers.factory import get_default_parsers
from specweaver.workspace.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.parsers.python.codestructure import PythonCodeStructure


def test_get_default_parsers() -> None:
    parsers = get_default_parsers()

    # Assert standard extensions are correctly mapped
    assert (".py",) in parsers
    assert isinstance(parsers[(".py",)], PythonCodeStructure)

    assert (".java",) in parsers
    assert isinstance(parsers[(".java",)], JavaCodeStructure)

    # Ensure tuples cover TS/TSX
    assert (".ts", ".tsx") in parsers
