from pathlib import Path


def test_polyglot_c_ast_integration(tmp_path: Path) -> None:
    c_file = tmp_path / "main.c"
    c_file.write_text(
        """
#include <stdio.h>
int main() {
    printf("hello");
    return 0;
}
""",
        encoding="utf-8",
    )

    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

    atom = CodeStructureAtom(cwd=tmp_path)

    # Test skeleton
    res = atom.run({"intent": "skeletonize", "path": "main.c"})
    skeleton = res.exports["structure"]
    assert "#include <stdio.h>" in skeleton
    assert "int main" in skeleton

    res = atom.run({"intent": "list_symbols", "path": "main.c"})
    symbols = res.exports["symbols"]
    assert "main" in symbols

    res = atom.run(
        {
            "intent": "replace_symbol_body",
            "path": "main.c",
            "symbol_name": "main",
            "new_code": "{\n    return 1;\n}",
        }
    )
    assert res.status.value == "SUCCESS"

    new_code = c_file.read_text(encoding="utf-8")
    assert "return 1;" in new_code

    # Test add_symbol
    res = atom.run(
        {
            "intent": "add_symbol",
            "path": "main.c",
            "target_parent": "main",
            "new_code": "int extra = 0;",
        }
    )
    assert res.status.value == "SUCCESS"
    assert "int extra = 0;" in c_file.read_text("utf-8")
