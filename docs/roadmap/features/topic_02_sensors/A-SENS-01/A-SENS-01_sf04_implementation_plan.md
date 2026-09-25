# A-SENS-01 SF-04 — Pipeline Execution Optimization

**Status**: APPROVED · **Feature ID**: 3.32 · **FRs owned**: NFR-1 · **Depends on**: SF-03 ·
Design: [A-SENS-01_design.md](A-SENS-01_design.md) §Sub-features → SF-04

## Goal

The orchestration engine (`QARunner`, `PipelineRunner`, `EngineFileExecutor`) consumes the
`stale_nodes` diff from SF-03 and skips clean nodes. The Semantic Cache is flushed ONLY after the
pipeline's validations succeed.

## Where it plugs in

`flow` and `graph` are siblings, consumed only by `cli` and `api` (the L1–L6 module dependency graph
in `architecture_reference.md`). They may not consume each other. So:

1. `flow` does NOT consume `graph`; `src/specweaver/core/flow/context.yaml` is unchanged.
2. `TopologyGraph` and `DependencyHasher` stay inside `assurance/graph`.
3. Staleness reaches the flow engine through `RunContext`; the cache flush lives in the `CLI`.

Rejected: **Option C** (dedicated handler in flow) and **Option A** (hook in `PipelineRunner` or
`QARunnerHandler`) — both make `flow` import `DependencyHasher`.

## Changes

1. **Post-validation cache flush** · `specweaver.cli`: `cli/project_commands.py` or the CLI entrypoints — after
   `runner.run()`, if the run succeeded, call `DependencyHasher.save_cache()`. If tests fail the
   cache is not updated, so the next loop still sees the stale nodes.
2. **Staleness bypass** · `specweaver.core.flow.engine`: `runner.py` `_execute_loop` reads `context.stale_nodes`:
   - `step_def.target != StepTarget.PROJECT` and not in `stale_nodes` → skip the step;
   - `step_def.target == StepTarget.PROJECT` → never skip; pass `stale_nodes` into the step payload so
     atoms can narrow to sub-paths.
3. **Target rewriting** · `specweaver.core.loom`: `qa_runner/atom.py` — in `_intent_run_tests`, `_intent_run_linter`, etc.:
   when `stale_nodes` is in the `context` and `target` is global (e.g. `.`), run one check per
   `stale_nodes` path and aggregate the results (a 1-minute full scan becomes a <200ms delta scan).
4. **Sandbox symlink** · `runner_utils.py` `setup_sandbox_caches` — append `.specweaver` to the cache
   directory list. The link is made through `FileSystemAtom` with `intent: symlink`, not raw
   `os.symlink` or `executor.py` (either would break the architecture boundary), so path-traversal
   checks still apply.

Do **not** modify `context.yaml` boundary configurations.

## Tests

| Kind | Case |
|---|---|
| Integration | a `clean` module is bypassed through the QARunner lifecycle |
| Integration | the `.specweaver` cache is symlinked into the sandbox and persists back |
| Manual | a full pipeline through `QARunner`; the CLI reports a `Bypass` for unchanged hashes |

## As built

**Since moved** (noted 2026-09-25): the bypass is `core/flow/engine/staleness.py`; target rewriting
is `_resolve_targets` in `core/flow/handlers/validation.py` (also read by `lint_fix.py`), not the
`qa_runner` atom; `setup_sandbox_caches` is in `core/flow/engine/sandboxed_execution.py`; the flush
is in `core/flow/interfaces/cli.py` (COMPLETED runs only). `stale_nodes` now sits on
`context.graph` and nothing writes it — see the design's Risks.
