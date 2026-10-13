# C-FLOW-06 — Phase 3 Optimizations: as built

**Design**: [C-FLOW-06_design.md](C-FLOW-06_design.md)

| File (`src/specweaver/`) | Holds | FRs |
|:---|:---|:---|
| `core/flow/handlers/prompting.py` | `_build_base_prompt`: one `api_contract` block per recorded contract outline | FR-1 |
| `core/flow/handlers/context_assembler.py` | outlines through `CodeStructureAtom` (`skeletonize`) | FR-1, NFR-1 |
| `assurance/graph/changes.py` | `changed_files`: per-file compare with the hash cache | FR-2 |
| `core/flow/handlers/changed_code.py` | `folders_to_test`: changed files to test folders, users included, none inside another | FR-2 |
| `core/flow/handlers/validation.py` | `ValidateTestsHandler._resolve_targets`; `tests_cover_project` in the step's output | FR-2 |
| `core/flow/interfaces/cli.py` | `_tests_passed_over_project`: the cache is saved only after green whole-project tests | FR-2 |
| `core/flow/engine/isolation.py` · `assurance/validation/interfaces/cli.py` | `seed_dal_level`; `sw check` strict on `DAL_A`/`DAL_B` | FR-3 |
| `workspace/project/scaffold.py` | `_scaffold_context_yaml` | FR-4 |
