# Implementation Plan: Archetype-Based Rule Sets [SF-3: Pure Logic Archetype Validators]
- **Feature ID**: 3.29
- **Sub-Feature**: SF-3 — Pure Logic Archetype Validators
- **Design Document**: docs/roadmap/phase_3/feature_3.29/feature_3.29_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.29/feature_3.29_sf3_implementation_plan.md
- **Status**: APPROVED

## 1. Goal
Implement the `C12` and `S12` generic Archetype validation rules. To maintain Trunk-based Layer bounds and pure mathematical safety, Markdown Documentation will be parsed structurally as a Native Language using `tree-sitter-markdown`. Support for modular baseline Plugin Yamls will be natively integrated into `workflows/pipelines/frameworks/`.

## 2. Research Notes
- **Resolving the `S12` LLM Ban:** The `rules/spec/context.yaml` completely forbids LLM boundaries for pure logic rules. To prevent violating this Architecture, `S12` will rely precisely on the `CodeStructureAtom` to extract Markdown AST boundaries exactly identical to `C12` extracting Python boundaries. 
- **Rule.context Initialization:** The executor directly maps dictionary parameters via `**kwargs`. We will formally append `self.context: dict` into the abstract `Rule` baseline class to seamlessly intercept orchestrator engine payloads.
- **Workflow Pipeline Modularity:** All framework archetype Yamls (e.g., `spring-boot`, `fastapi`) will completely leave `loom/` (execution bounds) and formally reside directly inside `workflows/pipelines/frameworks/<language>/`.

## 3. Proposed Changes

### `pyproject.toml`
#### [MODIFY] 
- Append `tree-sitter-markdown>=0.23` to the base dependencies.

### `src/specweaver/core/loom/commons/language/markdown/`
#### [NEW] `codestructure.py`
- Initialize `MarkdownCodeStructure` extending pure `CodeStructureAtom` APIs.
- Specifically support the `extract_skeleton` intent natively returning a JSON boundary of `Spec.md` H2/H3 headers and core paragraph bounds.

### `src/specweaver/core/flow/_validation.py`
#### [MODIFY] `ValidateSpecHandler`
- Align with `ValidateCodeHandler`: Run the `CodeStructureAtom` extraction on the `spec_path`.
- Inject the resulting DOM into the `ast_payload` parameter for `execute_validation_pipeline()`.

### `src/specweaver/assurance/validation/models.py`
#### [MODIFY] `Rule` ABC
- Formalize a `context: dict[str, Any]` property on the base Rule class preventing constructor parameter drops.

### `src/specweaver/assurance/validation/executor.py`
#### [MODIFY] `execute_validation_pipeline`
- Add runtime logic to assign `step.params.pop("ast_payload")` firmly to `rule.context = payload` before execution safely bridging payloads natively to pure logic targets.

### `src/specweaver/assurance/validation/rules/code/`
#### [NEW] `c12_archetype_code_bounds.py`
- Create `C12_ArchetypeCodeBounds(Rule)`.
- Validates structural mechanics inside `self.context["framework_markers"]`.
#### [MODIFY] `register.py`
- Register `C12`.

### `src/specweaver/assurance/validation/rules/spec/`
#### [NEW] `s12_archetype_spec_bounds.py`
- Create `S12_ArchetypeSpecBounds(Rule)`.
- Evaluates Spec Markdown boundaries structurally utilizing the `self.context["skeleton"]` Markdown AST parsed earlier via tree-sitter.
#### [MODIFY] `register.py`
- Register `S12`.

### `src/specweaver/assurance/validation/pipeline_loader.py`
#### [MODIFY] `_load_raw_yaml`
- Incorporate `importlib.resources.files("specweaver.workflows.pipelines.frameworks").iterdir()` searching mechanisms cleanly extending `ArchetypeResolver` parameters to natively fall back on plugin libraries.

### `src/specweaver/workflows/pipelines/frameworks/java/`
#### [NEW] `validation_code_spring-boot.yaml`
- Base Native configuration logic bounding Spring `@RestController` constraints across `C12`.
#### [NEW] `validation_spec_spring-boot.yaml`
- Base Native configuration logic bounding Spec.md architectural formatting blocks.

## 4. Backlog / Tech Debt
- **[Backlog] Markdown AST Mutators:** Formally implement `extract_symbols()` and `rewrite_symbol_body()` on the newly established `MarkdownCodeStructure` module. This treats Markdown headings (e.g. `## Intent`) natively as code block symbols, enabling surgical LLM refactoring of documentation to completely eliminate the blind-overwrite truncation risk for large Spec documents.

## 5. Verification Plan

### Automated Tests
1. **`tests/integration/core/loom/test_polyglot_ast_markdown.py`**
   - E2E assert that `CodeStructureAtom` gracefully extracts structural Markdown headers across `extract_skeleton`.
2. **`tests/unit/assurance/validation/rules/code/test_c12_archetype_code_bounds.py`**
   - Inject logical JSON context and map failure outcomes exactly to boundary requirements.
3. **`tests/unit/assurance/validation/rules/spec/test_s12_archetype_spec_bounds.py`**
   - Provide mathematical mappings confirming S12 passes valid Spec.md architecture DOM models.
4. **`tests/unit/assurance/validation/test_pipeline_loader.py`**
   - Verify `importlib` iterators mapping plugin parameters properly load from the underlying Language frameworks directory.
