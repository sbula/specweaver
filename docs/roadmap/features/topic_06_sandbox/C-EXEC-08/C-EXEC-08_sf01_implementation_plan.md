# Implementation Plan: Project Doc Policy [SF-01: The policy]
- **Feature ID**: C-EXEC-08
- **Sub-Feature**: SF-01 — The policy
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-08/C-EXEC-08_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-08/C-EXEC-08_sf01_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-19

**FRs owned**: FR-1, FR-2, FR-4, FR-5, FR-6 · **NFRs**: NFR-1, NFR-3, NFR-4 · **Depends on**: none

## Shape

| Piece | Where | Tag |
|---|---|---|
| `DocRule` (paths, access `human` / `open` / `step`, steps), `DocBlock` (file, name, step), `DocPolicy` (rules, blocks); strict, unknown keys refused | `core/config/doc_policy.py` | NEW |
| `parse_doc_policy(text, source)`: the `[docs]` section of `specweaver.toml`; a pattern holding `..` or absolute refused, a `step` rule without steps refused, each naming its line (NFR-1) | `core/config/doc_policy.py` | NEW |
| `load_doc_policy(project_root)`: reads the project's `specweaver.toml` through the same reader as `[llm]` | `core/config/bootstrap/` (next to `load_llm_settings`) | NEW |
| `doc_access(policy, path, step) -> "keep" \| "refuse" \| "task"`: the protected files refused whatever a rule says (NFR-3); the built-in rules, then the project's, the last matching one deciding (FR-5, Q8); `task` when no rule matches — the task's own allow-list then decides | `sandbox/security.py`, beside `path_allowed` (NFR-4) | NEW |

SF-01 builds the policy and its decision; SF-02 makes the task grant and the merge use it.

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the model, the parser, the loader | FR-1, NFR-1 | a `[docs]` section is rejected today as an unknown table, or ignored |
| CB-2 | `doc_access` | FR-2, FR-4, FR-5, FR-6, NFR-3, NFR-4 | there is no decision but `merge_keeps`' fixed rule |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit + integration | each key and its refusal, naming the line; a real project's `specweaver.toml` loaded from disk, with and without `[docs]` |
| CB-2 | unit | human, open and step rules; a `[docs]` that names only `docs/user_guides/**` leaves `README.md` and `docs/roadmap/` human (Q8); a named step and another step; last match wins both ways; no section keeps `README.md` and `docs/**` human; a rule that tries to open `.specweaver/` or `context.yaml` still refuses; `*` stays in one folder, `**` spans folders |

## Mutants (into `C-EXEC-08_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the `..` refusal; the empty-steps refusal | CB-1 tests |
| CB-2 | first match instead of last; the protected-file check; the built-in rules dropped; a `step` rule granting every step | CB-2 tests |

## Research Notes

- Today's single rule: `merge_keeps` (`sandbox/security.py:220-230`); patterns by `path_allowed`
  (`security.py:203-217`): `*` within a folder, `**` across folders, `..` refused.
- Protected names: `FileExecutor._PROTECTED_PATTERNS` (`sandbox/filesystem/core/executor.py:64-71`).
- The project file is read by `load_llm_settings` (`bootstrap/llm_settings_loader.py:36-49`) and
  parsed in `core.config` (`parse_project_llm`, `llm_settings.py:272`); `sandbox` may depend on
  `core.config` (`tach.toml`, `specweaver.sandbox`).

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q8 | With a `[docs]` section, do the built-in rules still apply to paths no project rule names? | yes: they come first and the project's rules after, so a path no project rule names keeps its protection `[agreed 2026-10-19]` |

## Backlog

none
