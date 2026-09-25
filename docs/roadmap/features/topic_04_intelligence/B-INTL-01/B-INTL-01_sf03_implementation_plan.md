# B-INTL-01 SF-03 — Pure Logic Archetype Validators

**Status**: APPROVED. Implemented (every change ✓). · **FRs owned**: FR-3, FR-4 · **Depends on**:
SF-01, SF-02 · Design: [B-INTL-01_design.md](B-INTL-01_design.md) §Sub-features → SF-03

## Goal

Add the generic archetype rules `C12` (code) and `S12` (spec). Specs are parsed as a language of
their own with `tree-sitter-markdown`, which keeps the layer bounds. Baseline framework plugin YAMLs
live in `workflows/pipelines/frameworks/`.

## Where it plugs in

- **`S12` and the LLM ban:** `rules/spec/context.yaml` forbids LLM use in pure-logic rules. So `S12`
  gets the Markdown AST from `CodeStructureAtom`, the same way `C12` gets the Python AST.
- **`Rule.context`:** the executor maps dictionary parameters via `**kwargs`. A `self.context: dict`
  on the abstract `Rule` base class catches the orchestrator's payload.
- **Pipeline YAMLs:** framework archetype YAMLs (e.g. `spring-boot`, `fastapi`) leave `loom/`
  (execution) and live in `workflows/pipelines/frameworks/<language>/`.

## Changes

| File | Change |
|------|--------|
| `pyproject.toml` | add `tree-sitter-markdown>=0.23` to the base dependencies |
| `src/specweaver/core/loom/commons/language/markdown/codestructure.py` [NEW] | `MarkdownCodeStructure`, on the `CodeStructureAtom` APIs; `extract_skeleton` returns a JSON outline of the `Spec.md` H1/H2/H3 headers |
| `src/specweaver/core/flow/_validation.py` — `ValidateSpecHandler` | as `ValidateCodeHandler`: run the `CodeStructureAtom` extraction on the `spec_path`; inject the result into the `ast_payload` parameter for `execute_validation_pipeline()` |
| `src/specweaver/assurance/validation/models.py` — `Rule` ABC | a `context: dict[str, Any]` property, so constructor parameters are not dropped |
| `src/specweaver/assurance/validation/executor.py` — `execute_validation_pipeline` | map `ast_payload` into `rule.context` (built with `.get`, not pop) |
| `src/specweaver/assurance/validation/rules/code/c12_archetype_code_bounds.py` [NEW] + `register.py` | `C12_ArchetypeCodeBounds(Rule)`: checks the structure inside `self.context["framework_markers"]`; registered |
| `src/specweaver/assurance/validation/rules/spec/s12_archetype_spec_bounds.py` [NEW] + `register.py` | `S12_ArchetypeSpecBounds(Rule)`: checks the Spec headings in the `self.context["structure"]` Markdown AST; registered |
| `src/specweaver/assurance/validation/pipeline_loader.py` — `_load_raw_yaml` | search `importlib.resources.files("specweaver.workflows.pipelines.frameworks").iterdir()`, so `ArchetypeResolver` names fall back on plugin libraries |
| `src/specweaver/workflows/pipelines/frameworks/java/validation_code_spring-boot.yaml` [NEW] | baseline: Spring `@RestController` constraints through `C12` |
| `src/specweaver/workflows/pipelines/frameworks/java/validation_spec_spring-boot.yaml` [NEW] | baseline: required Spec.md architecture blocks |

## Tests

| # | File | Case |
|---|------|------|
| 1 | `tests/integration/core/loom/test_polyglot_ast_markdown.py` | E2E: `CodeStructureAtom` extracts Markdown headers through `extract_skeleton` |
| 2 | `tests/unit/assurance/validation/rules/code/test_c12_archetype_code_bounds.py` | injected JSON context; failures map to the boundary requirements |
| 3 | `tests/unit/assurance/validation/rules/spec/test_s12_archetype_spec_bounds.py` | S12 passes a valid Spec.md DOM |
| 4 | `tests/unit/assurance/validation/test_pipeline_loader.py` | the `importlib` search loads plugin YAMLs from the frameworks directory |

## Backlog

**Markdown AST mutators:** implement `extract_symbols()` and `rewrite_symbol_body()` on
`MarkdownCodeStructure`. Markdown headings (e.g. `## Intent`) become symbols, so an LLM can edit one
section of a large Spec instead of overwriting it blind — which removes the truncation risk.

## As built

**Since changed** (checked 2026-09-25): `MarkdownCodeStructure` lives in
`src/specweaver/workspace/ast/parsers/markdown/codestructure.py`; `pyproject.toml` pins
`tree-sitter-markdown>=0.3.0`; the executor now pops `ast_payload` from a copy of the step params.
