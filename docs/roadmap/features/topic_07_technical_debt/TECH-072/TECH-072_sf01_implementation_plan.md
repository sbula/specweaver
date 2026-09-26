# TECH-072 SF-01 — Both Guards Applied

**Status**: APPROVED — approved by Steve Bula `[agreed 2026-09-26]` · **FRs owned**: FR-1, FR-2, FR-3,
FR-4, FR-5, FR-6, FR-7 · **Depends on**: none · Design: [TECH-072_design.md](TECH-072_design.md)

## Goal

Repair the agent AST tool and close the two latent holes, each guard shipped with the repair that
would have opened it. One commit boundary.

## Changes

| File | Change | FR |
|------|--------|-----|
| `src/specweaver/sandbox/security.py` | `normalize_grant_path`, `grant_mode_for`, `_path_under_grant` — the file tool's matcher, moved; `..` resolved after joining | FR-5, FR-6, FR-7 |
| `src/specweaver/sandbox/filesystem/interfaces/tool.py` | `_normalize_path` / `_resolve_mode` delegate to the shared matcher | FR-6 |
| `src/specweaver/sandbox/code_structure/interfaces/tool.py` | same delegation, resolved against `atom.cwd`; drifted copy deleted | FR-5, FR-6 |
| `src/specweaver/sandbox/code_structure/core/atom.py` | `cwd` property; a write the executor refuses returns FAILED | FR-1 |
| `src/specweaver/sandbox/dispatcher.py` | AST atom built on `FileExecutor`, not `EngineFileExecutor` | FR-1 |
| `src/specweaver/sandbox/mcp/core/atom.py` | `resolved_runtime_command` and `scrub_secrets` public — one copy for both paths | FR-4 |
| `src/specweaver/sandbox/mcp/interfaces/tool.py` | explorer runs the guard before starting a process and scrubs replies | FR-2, FR-3 |

## Tests

| Tier | File | Proves |
|---|---|---|
| Integration | `tests/integration/sandbox/test_agent_ast_tool_protected_paths.py` | FR-1, FR-5 |
| Integration | `tests/integration/sandbox/mcp/test_dispatcher_mcp_explorer_guard.py` | FR-2 |
| Unit | `tests/unit/sandbox/code_structure/core/code_structure/test_code_structure_atom_write_result.py` | FR-1 |
| Unit | `tests/unit/sandbox/test_grant_matching_agreement.py` | FR-6 |
| Integration | `tests/integration/sandbox/test_file_tool_stays_inside_root.py` | FR-7 |
| Unit | `tests/unit/sandbox/mcp/interfaces/mcp/test_mcp_explorer_guard.py` | FR-2, FR-3, FR-4 |

Mutation: [TECH-072_mutants.json](TECH-072_mutants.json), 6 mutants, all protected.

## As built (2026-09-26)

- Writing the first test showed the AST tool dead, not just unguarded: relative paths failed the
  grant matcher, absolute paths failed `FileExecutor`. The repair became FR-5 and FR-6.
- The atom discarded the executor's write result, so the executor swap alone would have reported a
  refused write as "Replaced symbol". Fixed with FR-1.
- The red/blue review found a live escape in the moved matcher: `grep(path="..")` read above the
  project. Fixed as FR-7, test first.
- Both holes were latent: no production path mounts the explorer (`architect` role), and the AST
  tool could not reach the executor. Recorded in the design.
- Existing tests adjusted, not weakened: `TestMCPExplorerTool` stands in a docker binary (the guard
  resolves it from `PATH`), and `test_code_structure_tool.py` gives its doubled atom a project root.
