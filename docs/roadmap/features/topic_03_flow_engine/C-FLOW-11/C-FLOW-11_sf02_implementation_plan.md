# Implementation Plan: Graduated Autonomy [SF-02: An agentic generate step]
- **Feature ID**: C-FLOW-11
- **Sub-Feature**: SF-02 — An agentic generate step
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-11/C-FLOW-11_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-11/C-FLOW-11_sf02_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-20

**FRs owned**: FR-3, FR-4, FR-5, FR-8, FR-9 · **NFRs**: NFR-3, NFR-4 · **Depends on**: SF-01
(committed 3dd67e9e)

## Shape

| Piece | Where | Tag |
|---|---|---|
| A code or tests generation step whose `resolve_execution_mode` decision is `agentic` runs the coder instead of the one-shot `Generator`; a refused one runs one-shot and puts the decision's reason in its result | `core/flow/handlers/generation.py` (`_GenerationHandler.execute`) | MODIFY |
| The coder: `ToolDispatcher.create_standard_set(boundary, role="implementer", allowed_tools=["ast"], task_files=[the step's own target], doc_policy=isolation.doc_policy, step=step.name)` over the step's project root (Q2). The target is repo-relative (`src/<stem>.py`, `tests/test_<stem>.py`) and only when `task_files(context)` holds it — a session allow-list without it leaves the coder nothing to write, and the step fails (Q1). The prompt is the one-shot prompt, artifact tagging included (`add_artifact_tagging`), plus an instruction to write the target with the tools | `core/flow/handlers/generation.py` | MODIFY |
| `InProcessAgentRuntime.run`: one `generate_with_tools` call; the adapter's `max_tool_rounds` (`[brake] agent_turns`) is the only turn limit; its own `max_turns` loop goes (AD-2) | `core/flow/engine/work_unit.py` | MODIFY |
| Reaching the limit: `ToolRoundsExceededError` becomes the step's failure, naming `brake.agent_turns`. A coder that ends without its target file fails the step, naming the file (Q1) | the handler's error path | MODIFY |
| An agentic step always isolates: `resolve_should_isolate` answers yes for it unless a session is active; a project that is not a git repo fails it, as isolation does today (AD-3) | `core/flow/engine/isolation.py` | MODIFY |
| A manifest or lock file (the design's list) outside the task's files is `propose`, not `strip` (AD-4) | `sandbox/security.py` (`write_verdict`'s task branch) | MODIFY |
| The waiting `E-SENS-03` e2e loses its `xfail` and gains a git repo | `tests/e2e/capabilities/sandbox/test_coder_writes_only_its_task_e2e.py` | MODIFY |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the runtime's single call; manifests proposed | FR-4, FR-5, FR-9, NFR-3 | a manifest change outside the task is stripped and lost |
| CB-2 | the agentic generate step: the coder, its grant, its worktree, its failure modes; the e2e | FR-3, FR-8, NFR-4 | `mode: agentic` makes no difference to a generate step |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit | the runtime makes one call and returns its text; a `ToolRoundsExceededError` and a spend stop pass through; `write_verdict` proposes `pyproject.toml` and `package-lock.json` outside the task, keeps one listed in it |
| CB-1 | integration | real git: a branch changing `pyproject.toml` → restored, its diff in `doc_updates.md` |
| CB-2 | integration | a scripted coder through the real handler, dispatcher and worktree: writes its target, lands; asks to write `README.md` → refused by the grant; asks for another module → refused; the tests step asks to change the module → refused (Q2); ends without its target → the step fails naming it (Q1); a session allow-list without the target → the step fails; a manifest → proposed; hits `agent_turns` → the step fails naming it; a DAL above the ceiling → one-shot, with the reason in the result |
| CB-2 | e2e | `sw run` with an agentic `generate code` step in a git project with a ceiling: the coder's `src/greeter.py` lands, its `README.md` write is refused and the file unchanged (the `E-SENS-03` journey, no longer `xfail`) |

## Mutants (into `C-FLOW-11_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | manifests stripped again; the runtime's tool loop dropped | CB-1 tests |
| CB-2 | the coder given no step name; the coder given no doc policy; agentic not isolated; the reason dropped from the result; the agentic path never taken | CB-2 tests |

## Research Notes

- Generation today: `_GenerationHandler.execute` (`generation.py:120-228`) builds the prompt with
  `_generation_prompt`, calls `Generator`, and returns `{"generated_path": ...}`; the target is
  `output_dir / f"{FILENAME_PREFIX}{stem}.py"`, `stem = spec_path.stem.replace("_spec", "")`.
- Routing: `_resolve_generation_routing` → `llm_for(context, TaskType.IMPLEMENT)` gives the adapter
  and a `GenerationConfig` whose `max_tool_rounds` is `[brake] agent_turns` (`resolve.py:106`).
- The tool loop runs inside `generate_with_tools(messages, config, dispatcher)`; past the limit it
  raises `ToolRoundsExceededError.reached` (`errors.py:56-72`), naming the setting.
- The implementer gets read grants on its roots and a `TaskGrant` on its task files
  (`dispatcher.py:27-29`, `_compute_role_grants`); `task_files(context)` is the session's allow-list,
  else `src/<stem>.py` and `tests/test_<stem>.py` (`isolation.py:40-60,103-110`).
- Per-step isolation reads `context.isolation.doc_policy` and the step's name already (`C-EXEC-08`
  SF-02), and merges `allowed_paths or derive_allowed_paths(spec)`.
- The waiting e2e (`test_coder_writes_only_its_task_e2e.py`) runs `sw init` with no `git init`;
  under FR-8 its project needs one, and `[autonomy]` with a ceiling.
- `InProcessAgentRuntime` (`work_unit.py:59-113`) loops `max_turns` times around
  `generate_with_tools`, which already loops the tools: two limits for one job (AD-2).

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | The coder ends without writing its target file: what then? | the step fails, naming the file `[agreed 2026-10-20]` |
| Q2 | Which files may one agentic step write? | only its own target — the code step its module, the tests step its test file — within the `[docs]` rules `[agreed 2026-10-20]` |

## Backlog

none
