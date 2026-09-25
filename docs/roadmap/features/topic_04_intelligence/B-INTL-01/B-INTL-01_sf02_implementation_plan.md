# B-INTL-01 SF-02 — Commons Framework Schema

**Status**: APPROVED. Implemented. · **FRs owned**: FR-2 · **Depends on**: SF-01 · Design:
[B-INTL-01_design.md](B-INTL-01_design.md) §Sub-features → SF-02

## Goal

Extract framework markers — decorators, annotations, macros, inheritance — from user code into a
JSON structure, without putting C-bindings in the pure-logic `assurance` layer. `CodeStructureInterface`
gains a method that returns these as a mapping, built from generic `.scm` Tree-Sitter queries.

Everything that uses `tree-sitter` lives in `loom/commons/language`.

## Changes

1. **Interface** · `src/specweaver/core/loom/commons/language/interfaces.py` — add
   `@abstractmethod def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:`
   to `CodeStructureInterface`. The dict maps a symbol name (e.g. `"MyController"`) to an inner dict
   with at least `"decorators"` and `"extends"`.
2. **Atom** · `src/specweaver/core/loom/atoms/code_structure/atom.py` — add
   `extract_framework_markers` to `valid_intents`; add `_handle_extract_framework_markers()`, which
   calls the parser and returns the dict under the `exports={"markers": ...}` key.
3. **Validation ingress** (refines SF-01) · `src/specweaver/core/flow/_validation.py` —
   `ValidateCodeHandler._run_validation` runs **both** intents on `CodeStructureAtom`, so the
   `ast_payload` holds the structure string and the marker dicts:

   ```python
   payload_res = atom.run({"intent": "extract_skeleton", "path": str(code_path)})
   markers_res = atom.run({"intent": "extract_framework_markers", "path": str(code_path)})
   ast_payload = {"structure": payload_res.exports.get("structure", "")}
   if markers_res.status.value == "SUCCESS":
       ast_payload["markers"] = markers_res.exports.get("markers", {})
   ```

4. **Language parsers** — each module defines an `SCM_MARKERS_QUERY` string that groups identifiers,
   and implements `extract_framework_markers(self, code: str)`:

| File | `SCM_MARKERS_QUERY` targets |
|------|------|
| `src/specweaver/core/loom/commons/language/python/codestructure.py` | `decorated_definition`; `class_definition` arguments (bases) |
| `src/specweaver/core/loom/commons/language/java/codestructure.py` | `class_declaration` (modifiers, superclass, interfaces); `method_declaration` (modifiers) |
| `src/specweaver/core/loom/commons/language/typescript/codestructure.py` | decorators; `class_heritage` clauses |
| `src/specweaver/core/loom/commons/language/rust/codestructure.py` | `attribute_item` on functions/structs; trait implementations (`impl_item`) |
| `src/specweaver/core/loom/commons/language/kotlin/codestructure.py` | modifiers (annotations); delegates/bases |

## Tests

| Tier | File / Case |
|---|---|
| Unit | `pytest tests/unit/core/flow/test_handlers_di_payload.py` — `ast_payload` merge |
| Integration | `tests/integration/loom/test_polyglot_ast_edge_cases.py` — Python/Java class files; the dicts hold the right `{"decorators": [...], "extends": [...]}` |

Manual verification happens in SF-03, which builds the `C12` rule on this payload.

## As built

**Since moved** (checked 2026-09-25): parsers live in `src/specweaver/workspace/ast/parsers/`; the
handler in `core/flow/handlers/validation.py` stores the markers under
`ast_payload["framework_markers"]` (the key `C12` reads), not `"markers"`.
