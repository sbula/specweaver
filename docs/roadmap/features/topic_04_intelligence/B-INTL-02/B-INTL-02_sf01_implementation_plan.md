# B-INTL-02 SF-01 — Core Schema Evaluator Engine

**Status**: APPROVED · **FRs owned**: FR-1, FR-2 (macro evaluation against declarative YAML schemas;
the multi-language gate — recorded 2026-08-17 under `specweaver-dev` §3.2c, from
`INT-US-05-SF04-MIG`) · **Depends on**: none · Design: [B-INTL-02_design.md](B-INTL-02_design.md)
§Sub-features → SF-01

## Goal

`evaluator.py` parses declarative YAML framework schemas and turns raw AST framework markers into
runtime explanations an LLM can read. The orchestrator injects the schemas (layer limits), and
cascading lookups are bounded (security).

## Where it plugs in

- **`context.yaml` restriction** (decided in Phase 4): `evaluator.py` in `commons/language` may not
  load YAMLs from `workflows/evaluators/`. The pipeline flow injects `evaluator_schemas: dict` into
  the `CodeStructureAtom` runtime.
- **Output shape:** no nested JSON. The evaluator's strings are prepended as line comments inside
  the raw source returned by the `read_unrolled_symbol` intent.
- **Security (NFR-4):** the parser is pure; `ruamel.yaml` runs in safe mode; no string formatting or
  `eval()` bindings on the mappings.
- **Recursion (NFR-5):** an integer cap, `MAX_EVALUATOR_DEPTH = 5`, stops cyclic-mapping OOMs.

## Changes

1. **[NEW] `src/specweaver/core/loom/commons/language/evaluator.py`** — `class SchemaEvaluator`:
   - constructor takes `schemas: dict[str, Any]` (already loaded in memory);
   - `evaluate_markers(language: str, markers: dict) -> str` returns one readable paragraph in the
     language's comment style (e.g. `//` for Java/TS, `#` for Python);
   - `MAX_EVALUATOR_DEPTH = 5` plus cycle tracking `visited = set()` across cascading definitions.
2. **`src/specweaver/core/loom/atoms/code_structure/atom.py`** — `CodeStructureAtom.__init__` takes an
   optional `evaluator_schemas: dict = None`. New intent `read_unrolled_symbol`:
   1. run `extract_framework_markers()`;
   2. evaluate with `SchemaEvaluator`;
   3. put the explanation block directly above the output of `extract_symbol()`.
3. **`src/specweaver/core/loom/tools/code_structure/tool.py`** — `read_unrolled_symbol` method,
   delegating to the atom; standard file-read access bounds. `ROLE_INTENTS` whitelists it for
   `implementer` and `reviewer`.
4. **`src/specweaver/core/loom/tools/code_structure/definitions.py`** — `READ_UNROLLED_SYMBOL_SCHEMA`,
   saying why it beats a plain read.
5. **`src/specweaver/core/flow/_validation.py`** (orchestrator, FR-4) — load the ecosystem YAML
   evaluators via `importlib.resources.files` before entering Executor isolation; pass them down as
   dict kwargs to the tool.

SF-02 writes the framework libraries (Spring Boot, NestJS, …); here the DI loader only loads, it does
not validate definitions.

## Tests

| # | File | Case |
|---|------|------|
| 1 | [NEW] `tests/unit/core/loom/commons/language/test_schema_evaluator.py` | `MAX_EVALUATOR_DEPTH` stops cascading loops; marker dicts → language-aware comment blocks |
| 2 | [NEW] `tests/integration/core/loom/test_code_structure_tool_evaluator.py` | mocked schema injection; `read_unrolled_symbol` adds comment headers without breaking tree-sitter semantics |

Current proof and mutants: `tests/integration/sandbox/test_code_structure_tool_evaluator.py`.

## As built

- `load_evaluator_schemas(project_dir)` deep-merges project-local schemas (`.specweaver/evaluators/`)
  over the default ecosystem payloads (FR-4, NFR-3); covered by an integration flow test.
- **Since moved** (checked 2026-09-25): `SchemaEvaluator` lives in
  `src/specweaver/sandbox/language/core/evaluator.py`.
