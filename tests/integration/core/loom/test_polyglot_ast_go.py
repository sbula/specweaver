from pathlib import Path


def test_polyglot_go_ast_integration(tmp_path: Path) -> None:
    go_file = tmp_path / "main.go"
    go_file.write_text(
        """
package main

import "fmt"

type Engine struct {}

func (e *Engine) Run() int {
    return 0
}
""",
        encoding="utf-8",
    )

    from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom

    atom = CodeStructureAtom(cwd=tmp_path)

    # Test skeleton
    res = atom.run({"intent": "skeletonize", "path": "main.go"})
    skeleton = res.exports["structure"]
    assert "type Engine struct" in skeleton

    # Test list symbols with visibility
    res = atom.run({"intent": "list_symbols", "path": "main.go", "visibility": ["public"]})
    symbols = res.exports["symbols"]
    assert "Engine.Run" in symbols
    assert "Engine" in symbols

    # Test read_symbol
    res = atom.run({"intent": "read_symbol", "path": "main.go", "symbol_name": "Engine.Run"})
    assert "func (e *Engine) Run() int {" in res.exports["symbol"]
    assert "return 0" in res.exports["symbol"]

    # Test delete_symbol
    res = atom.run({"intent": "delete_symbol", "path": "main.go", "symbol_name": "Engine.Run"})
    assert res.status.value == "SUCCESS"
    assert "func (e *Engine) Run() int" not in go_file.read_text("utf-8")

    # Test extract_framework_markers
    res = atom.run({"intent": "extract_framework_markers", "path": "main.go"})
    assert res.status.value == "SUCCESS"
    assert res.exports["markers"] == {}



def test_polyglot_go_edge_cases(tmp_path: Path) -> None:
    go_file = tmp_path / "edge.go"
    go_file.write_text(
        """
package edge

import "fmt"

type (
    A struct {
        val int
    }
    B interface {
        Do()
    }
)

func (a *A) Run() {}
func (a A) RunValue() {}
""",
        encoding="utf-8",
    )

    from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom

    atom = CodeStructureAtom(cwd=tmp_path)

    # Test grouped type extraction and replacement (Story 10)
    res = atom.run({"intent": "read_symbol", "path": "edge.go", "symbol_name": "A"})
    assert "A struct {" in res.exports["symbol"]
    assert "B interface" not in res.exports["symbol"]

    new_a = "A struct { newval string }"
    res = atom.run({"intent": "replace_symbol", "path": "edge.go", "symbol_name": "A", "new_code": new_a})
    assert res.status.value == "SUCCESS"

    # Reload file text, Atom replaced it directly
    content = go_file.read_text("utf-8")
    assert "A struct { newval string }" in content
    assert "B interface" in content
    assert "type (" in content

    # Test interface and value receiver methods (Story 12)
    res = atom.run({"intent": "read_symbol", "path": "edge.go", "symbol_name": "B"})
    assert "B interface" in res.exports["symbol"]

    res = atom.run({"intent": "read_symbol", "path": "edge.go", "symbol_name": "A.RunValue"})
    assert "func (a A) RunValue() {}" in res.exports["symbol"]
