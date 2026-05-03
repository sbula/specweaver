from pathlib import Path


def test_e2e_cpp_flow(tmp_path: Path) -> None:
    # Set up project
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    cpp_file = project_dir / "calc.cpp"
    cpp_file.write_text(
        """
class Calculator {
public:
    int add(int a, int b) { return a + b; }
};
""",
        encoding="utf-8",
    )

    # The flow engine uses context assemblers, validators, etc.
    # To keep this simple and fast, we simulate a pipeline step that targets a C++ file
    # and replaces a symbol's body via the CodeStructureAtom.

    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

    atom = CodeStructureAtom(cwd=project_dir)

    # Extract
    res = atom.run({"intent": "read_symbol", "path": "calc.cpp", "symbol_name": "Calculator.add"})
    assert res.status.value == "SUCCESS"
    assert "return a + b;" in res.exports["symbol"]

    # Mutate
    res_write = atom.run(
        {
            "intent": "replace_symbol_body",
            "path": "calc.cpp",
            "symbol_name": "Calculator.add",
            "new_code": "{\n    return a - b;\n}",
        }
    )
    assert res_write.status.value == "SUCCESS"

    # Verify File
    content = cpp_file.read_text(encoding="utf-8")
    assert "return a - b;" in content
