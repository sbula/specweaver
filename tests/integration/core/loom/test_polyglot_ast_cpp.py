from pathlib import Path

def test_polyglot_cpp_ast_integration(tmp_path: Path) -> None:
    cpp_file = tmp_path / "main.cpp"
    cpp_file.write_text(
        """
#include <iostream>
class Engine {
public:
    [[nodiscard]] int run() { return 0; }
};
""",
        encoding="utf-8",
    )

    from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom

    atom = CodeStructureAtom(cwd=tmp_path)

    # Test skeleton
    res = atom.run({"intent": "skeletonize", "path": "main.cpp"})
    skeleton = res.exports["structure"]
    assert "class Engine" in skeleton

    # Test visibility and decorator filtering
    res = atom.run({"intent": "list_symbols", "path": "main.cpp", "decorator_filter": "nodiscard"})
    symbols = res.exports["symbols"]
    assert "run" in symbols
    assert "Engine" not in symbols

    # Test imports (not natively exposed via Atom intents, but we can verify it doesn't crash)
    # The atom intent 'read_file_structure' is typically used for skeleton.
    # We will test read_symbol
    res = atom.run({"intent": "read_symbol", "path": "main.cpp", "symbol_name": "run"})
    assert "int run() { return 0; }" in res.exports["symbol"]

    # Test delete_symbol
    res = atom.run({"intent": "delete_symbol", "path": "main.cpp", "symbol_name": "run"})
    assert res.status.value == "SUCCESS"
    assert "int run()" not in cpp_file.read_text("utf-8")

    # Test extract_framework_markers
    res = atom.run({"intent": "extract_framework_markers", "path": "main.cpp"})
    assert res.status.value == "SUCCESS"
    assert res.exports["markers"] == {}
