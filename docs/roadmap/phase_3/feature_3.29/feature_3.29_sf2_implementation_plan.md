# Implementation Plan: Archetype-Based Rule Sets [SF-2: Commons Framework Schema]
- **Feature ID**: 3.29
- **Sub-Feature**: SF-2 — Commons Framework Schema
- **Design Document**: docs/roadmap/phase_3/feature_3.29/feature_3.29_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.29/feature_3.29_sf2_implementation_plan.md
- **Status**: APPROVED

## 1. Overview
Feature 3.29 SF-2 requires extracting polyglot framework markers (decorators, annotations, macros, and inheritance) from user code safely into a JSON structure, without polluting the Pure Logic `assurance` layer with C-bindings. 
This plan extends the `CodeStructureInterface` to return rich mapping payloads dynamically using generalized `.scm` Tree-Sitter queries. 

## 2. Proposed Changes

All structural extraction logic relies heavily on `tree-sitter` and must therefore reside in `loom/commons/language`, strictly isolated from the pure-logic `assurance` boundaries.

### 2.1 Interface & Atom Extensions 
We expand the core DI contract so that Validation has access to structured JSON data.

#### [MODIFY] src/specweaver/core/loom/commons/language/interfaces.py
- **Changes**: Add `@abstractmethod def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:` to `CodeStructureInterface`.
- **Note**: The returned dictionary should map the symbol name (e.g., `"MyController"`) to an inner dictionary containing at least `"decorators"` and `"extends"`.

#### [MODIFY] src/specweaver/core/loom/atoms/code_structure/atom.py
- **Changes**: 
  - Add `extract_framework_markers` to `valid_intents`.
  - Add `_handle_extract_framework_markers()` which calls the parser and returns the dictionary under the `exports={"markers": ...}` key.

### 2.2 Validation Ingress Update (SF-1 Refinement)
#### [MODIFY] src/specweaver/core/flow/_validation.py
- **Changes**: In `ValidateCodeHandler._run_validation`, the `ast_payload` is natively built via `extract_skeleton`. We must now run **both** intents sequentially or in parallel against the `CodeStructureAtom` so the `ast_payload` passed to the Rule contains both the structural string and the framework dictionaries:
  ```python
  payload_res = atom.run({"intent": "extract_skeleton", "path": str(code_path)})
  markers_res = atom.run({"intent": "extract_framework_markers", "path": str(code_path)})
  ast_payload = {"structure": payload_res.exports.get("structure", "")}
  if markers_res.status.value == "SUCCESS":
      ast_payload["markers"] = markers_res.exports.get("markers", {})
  ```

### 2.3 Polyglot Language Parsers
We implement `extract_framework_markers` in every supported language utilizing generic agnostic capture points to extract dynamically all meta-markers into the JSON format. 
To do this, each module must define an `SCM_MARKERS_QUERY` string that groups identifiers.

#### [MODIFY] src/specweaver/core/loom/commons/language/python/codestructure.py
- Add `SCM_MARKERS_QUERY` targeting `decorated_definition` and `class_definition` arguments (bases).
- Implement `extract_framework_markers(self, code: str)`.

#### [MODIFY] src/specweaver/core/loom/commons/language/java/codestructure.py
- Add `SCM_MARKERS_QUERY` targeting `class_declaration` (modifiers, superclass, interfaces) and `method_declaration` (modifiers).
- Implement `extract_framework_markers(self, code: str)`.

#### [MODIFY] src/specweaver/core/loom/commons/language/typescript/codestructure.py
- Add `SCM_MARKERS_QUERY` targeting decorators and `class_heritage` clauses.
- Implement `extract_framework_markers(self, code: str)`.

#### [MODIFY] src/specweaver/core/loom/commons/language/rust/codestructure.py
- Add `SCM_MARKERS_QUERY` targeting `attribute_item` on functions/structs, and trait implementations (`impl_item`).
- Implement `extract_framework_markers(self, code: str)`.

#### [MODIFY] src/specweaver/core/loom/commons/language/kotlin/codestructure.py
- Implement equivalent Kotlin Tree-Sitter support for modifiers (Annotations) and delegates/bases.

## 3. Verification Plan

### Automated Tests
- Run `pytest tests/unit/core/flow/test_handlers_di_payload.py` to ensure `ast_payload` merging works smoothly.
- Create tests for Python/Java in `tests/integration/loom/test_polyglot_ast_edge_cases.py` passing generic class files and asserting the dictionaries contain accurate `{"decorators": [...], "extends": [...]}` captures.

### Manual Verification
- Execution of this plan fully enables SF-3, which builds the `C12` pure logic boundary rule. Successful manual verification will happen when building out SF-3 next.
