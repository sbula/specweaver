# Implementation Plan: Two Agent Tools Skip the Sandbox's Own Guards [SF-02: The two open calls]
- **Feature ID**: TECH-072
- **Sub-Feature**: SF-02 — The two open calls
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-072/TECH-072_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-072/TECH-072_sf02_implementation_plan.md
- **Status**: APPROVED — built 2026-10-17 from the user's two answers to the review's open calls

**FRs owned**: FR-8, FR-9 · **Depends on**: SF-01

| Piece | Where | FR |
|---|---|---|
| `refuse_loader_env(env)` beside the runtime guard, called by `MCPAtom` and `MCPExplorerTool` before any process starts | `sandbox/mcp/core/atom.py`, `sandbox/mcp/interfaces/tool.py` | FR-8 |
| protected names compared without case: the file executor and `merge_keeps` | `sandbox/filesystem/core/executor.py`, `sandbox/security.py` | FR-9 |

| Tier | Test | FR |
|---|---|---|
| Unit | `tests/unit/sandbox/mcp/interfaces/mcp/test_mcp_loader_env_refused.py` — both paths, red first (16 failed) | FR-8 |
| Unit | `tests/unit/sandbox/test_protected_names_ignore_case.py` — executor and merge rule, red first | FR-9 |

Mutants: `explorer-passes-loader`, `atom-passes-loader`, `executor-case-sensitive`,
`merge-rule-case-sensitive`; also `file-tool-own-root` for FR-6, which had none.
