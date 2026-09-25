# B-INTL-02 SF-03 — Tool Intent & Guide Publishing

**Status**: APPROVED · **Depends on**: SF-02 · Design: [B-INTL-02_design.md](B-INTL-02_design.md)
§Sub-features → SF-03

## Goal

Publish `read_unrolled_symbol` and document the macro/annotation unroll pattern in the developer
guides, so other teams can add frameworks.

## Where it plugs in

- **Intent already wired:** SF-01/SF-02 added `read_unrolled_symbol` to
  `src/specweaver/core/loom/tools/code_structure/tool.py` and its LLM JSON schema to `definitions.py`.
  Routing to the evaluator works; no code change needed.
- **Guide gap:** `docs/dev_guides/adding_framework_guide.md` covers only validation rules on
  archetypes (the `spring-boot.yaml` pipeline). It does not say how to add or change the
  `frameworks/*.yaml` *Schema Evaluators* that `CodeStructureAtom` uses to unroll annotations.

## Changes

1. **`adding_framework_guide.md`** — new section "Step 1b: Defining Framework Schema Evaluators
   (Macro Unrolling)":
   - the LSP-bypass architecture;
   - how to map `@RestController` (or a company's own `@AuthBase` API classes) to YAML, in
     `src/specweaver/workflows/evaluators/frameworks/<archetype>.yaml`;
   - the `metadata.supported_languages` binding constraint.

## Tests

No Python changes, so no boundary risk. Markdown format checked by the pre-commit standards.
