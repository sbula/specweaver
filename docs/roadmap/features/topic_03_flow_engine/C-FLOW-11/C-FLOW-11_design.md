# C-FLOW-11 — Graduated Autonomy (DAL-Driven Execution-Mode Dial)

**Status**: APPROVED by the user 2026-10-20 — re-designed with them 2026-10-19 (Q1–Q13). The dial, its DAL check and the
tool loop were built earlier and never approved; this design is what they become. · **DAL**: C
(Enterprise Standard) — the dial is itself assurance policy. · **Epic**: Topic 03 (Flow
Orchestration) · **Feature ID**: C-FLOW-11

| | |
|---|---|
| Uses | `C-VAL-03` + `B-FLOW-07` (the run's DAL: nearest `context.yaml`, else the project's default `DAL_C`) · `C-EXEC-06` / `D-EXEC-02` (the worktrees and their merge) · `E-INTL-01` (the adapter's tool loop) · `E-SENS-03` (the task grant) · `C-EXEC-08` (the project's `[docs]` rules and proposals) · `B-FLOW-05` (spend) · `C-FLOW-13` (`[brake] agent_turns`) |
| Enables | `D-INTL-07` → extends the dial to draft steps, with its own tools `[agreed 2026-10-19]` · `B-INTL-06` → multi-agent work |
| Not touched | the one-shot handlers; what an agent may read; draft, review and plan steps `[agreed 2026-10-19]` |

## Feature Overview

A pipeline step may say `mode: agentic`. The project's `specweaver.toml` says how far agentic work
may go, by the risk level (DAL) of the code. An agentic `generate` step then runs the coder in a
tool loop: it reads the code, writes its task's files through its tools, and corrects itself,
inside a worktree. Everything it writes passes the task grant and the project's `[docs]` rules
when it writes, and the merge when the step ends.

Today the dial is built but no user reaches it: no handler reads `mode`, the tool loop is called
only by its own tests, and `[autonomy]` is never read from any file. Measured 2026-10-19.

## Research Findings

### Codebase Patterns

- The dial: `resolve_execution_mode(step_def, context)` (`core/flow/engine/autonomy.py:55`) reads
  `isolation.autonomy` and `isolation.dal_level`; `AutonomySettings(mode, agentic_max_dal=DAL_D,
  max_turns=10)` (`core/config/settings.py:92-111`) — defaults nobody agreed, never loaded from a
  file (`settings_loader.py` reads only `[standards]` and `[sandbox]`).
- The run's DAL is always set: `seed_dal_level` (`isolation.py:161-174`, called by the runner) takes
  the nearest `context.yaml`, else the project default `DAL_C` (`workspace/store.py:34`), as
  `B-FLOW-07` FR-3 agreed.
- The tool loop: `LLMAdapter.generate_with_tools(messages, config, dispatcher)` runs the tools and
  stops at `config.max_tool_rounds`, which is `[brake] agent_turns`
  (`infrastructure/llm/resolve.py:106`); past it, `ToolRoundsExceededError.reached` names the
  setting. `InProcessAgentRuntime` (`work_unit.py:59-113`) wraps that call in a second loop with
  its own `max_turns` — two limits for one job.
- The coder's tools: `ToolDispatcher.create_standard_set(boundary, role, allowed_tools, task_files=,
  doc_policy=, step=)` (`sandbox/dispatcher.py`); `task_files(context)` (`isolation.py:103`). The
  e2e `test_coder_writes_only_its_task_e2e.py` waits on this as `xfail(strict=True)`.
- Worktrees: a step gets its own when `resolve_should_isolate` says so (`isolation.py:24-37`), or
  runs in the session's (`session.py`). `sw implement` turns sessions on by itself only at DAL-B
  and above (`apply_session_policy(..., dal_auto_escalate=True)`).
- The merge: `write_verdict` (`sandbox/security.py`) — `keep`, `propose`, `strip`; proposals go to
  the root `doc_updates.md` (`C-EXEC-08`).

### External Tools

None new.

### Blueprint References

Claude Code and Aider: an agent edits through tools inside a checkout, and a person reviews the
result. Neither installs dependencies on its own authority.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Rigidity is declarable, and today's behaviour is the default | Pipeline | SHALL read a step's `mode: oneshot \| agentic`, else the project's `[autonomy] mode`, else `oneshot` | a pipeline written before the dial runs as before |
| FR-2 | Criticality overrules the author | Runner | SHALL refuse `agentic` for a run whose DAL is riskier than `[autonomy] agentic_max_dal`; with no `agentic_max_dal` set, SHALL refuse every agentic step, naming the setting `[agreed 2026-10-19]` | a high-risk target stays deterministic, and no number nobody chose decides |
| FR-3 | An agentic step iterates | Generate handler | SHALL run the coder in one tool loop over the run's adapter with the code-structure tools only `[agreed 2026-10-19]`, writing through the task grant and the `[docs]` rules for its own step name (**seam**: `E-SENS-03`, `C-EXEC-08`) | the coder reads, writes and corrects within one step, and can write nothing its task does not cover |
| FR-4 | The loop cannot run away | Generate handler | SHALL bound the loop by `[brake] agent_turns` alone — no second turn limit `[agreed 2026-10-19]` — and by the run's spend limits; reaching the turn limit fails the step, naming it `[agreed 2026-10-19]` | cheap endless tool calls and costly ones both stop |
| FR-5 | The runtime is replaceable | Engine | SHALL depend only on the `AgentRuntime` protocol | a second runtime costs a class |
| FR-6 | The policy is the project's | Settings loader | SHALL read `[autonomy]` (`mode`, `agentic_max_dal` `[agreed 2026-10-19]`) from the project's `specweaver.toml` `[agreed 2026-10-19]`, strictly: an unknown key or value stops the command, naming the line | each project sets its own risk policy, reviewed like code |
| FR-7 | Only generate steps go agentic | Pipeline loader | SHALL refuse `mode: agentic` on any step that is not a `generate` step, when the pipeline loads `[agreed 2026-10-19]` | a reviewer or a drafter never gets write tools by a typo |
| FR-8 | Always in a worktree | Runner | SHALL run an agentic step in a worktree — its own, or the run's session — and refuse it only when the project is not a git repo `[agreed 2026-10-19]` (**seam**: `C-EXEC-06`, `D-EXEC-02`) | every agentic write passes two walls: the grant when written, the merge when the step ends |
| FR-9 | No new dependency by the model | Merge | SHALL keep a change to a dependency manifest or lock file that is not among the task's files as a proposal in `doc_updates.md`, instead of stripping it; the coder's task files never name one `[agreed 2026-10-19]` (**seam**: `C-EXEC-08`) | adding outside code stays the user's decision, and the change is not lost; a manifest a user lists in the task's files still lands |
| FR-10 | `sw implement` follows the dial | `sw implement` | SHALL run its generate steps agentic where the project's `[autonomy]` and the DAL allow it, with no new flag `[agreed 2026-10-19]` | the main command gains agentic work without a second way to ask for it |

The manifests of FR-9: `pyproject.toml`, `uv.lock`, `requirements*.txt`, `package.json`,
`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `pom.xml`, `build.gradle`, `build.gradle.kts`,
`Cargo.toml`, `Cargo.lock`, `go.mod`, `go.sum` `[agreed 2026-10-19]`. SpecWeaver's prepare phase
installs from them; the coder never installs.

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-2 | the run's DAL | `B-FLOW-07` · `seed_dal_level(context)` | read `isolation.py:161-174` |
| FR-6 | the project's settings text | `core.config.bootstrap` · `read_settings_text` | read `llm_settings_loader.py`, as `load_doc_policy` does |
| FR-3 | a tool loop | `E-INTL-01` · `generate_with_tools(messages, config, dispatcher)` | read `infrastructure/llm/adapters/base.py` |
| FR-3 | the coder's tools under its grant | `E-SENS-03` + `C-EXEC-08` · `create_standard_set(..., task_files=, doc_policy=, step=)` | read `sandbox/dispatcher.py` |
| FR-4 | the round limit | `C-FLOW-13` · `GenerationConfig.max_tool_rounds` ← `[brake] agent_turns` | read `resolve.py:106`, `errors.py:56-72` |
| FR-8 | a worktree for one step | `C-EXEC-06` · `resolve_should_isolate`, `execute_in_sandbox` | read `isolation.py:24-37`, `sandboxed_execution.py` |
| FR-9 | the merge's verdict | `C-EXEC-08` · `write_verdict` | read `sandbox/security.py` |

## Non-Functional Requirements

| # | NFR | Rule |
|---|---|---|
| NFR-1 | Zero regression | With no `mode: agentic` and no `[autonomy]`, every pipeline and `sw implement` run exactly as before |
| NFR-2 | Fail closed | No ceiling set, a broken `[autonomy]`, `agentic` on a non-generate step, or a project that is not a git repo: each refuses, naming the cause |
| NFR-3 | Two bounds | Turns and spend stay independent; neither replaces the other |
| NFR-4 | The walls stay | An agentic coder can write nothing the task grant, the `[docs]` rules and the protected names forbid |

## Settings shape `[agreed 2026-10-19]`

```toml
[autonomy]
mode = "oneshot"            # oneshot | agentic — the project's default for its steps
agentic_max_dal = "DAL_D"   # no default: agentic is refused until it is set
```

## External Dependencies

None.

## Architectural Decisions

| # | Decision | Why |
|---|---|---|
| AD-1 | `[autonomy]` is parsed in `core.config` beside `[docs]` and loaded by the run roots that load the doc policy | one reader of `specweaver.toml`, strict, at the edge (`ADR-002`) |
| AD-2 | `InProcessAgentRuntime` makes one `generate_with_tools` call; the adapter's round limit is the only turn limit | the second loop was a second limit for the same job (FR-4) |
| AD-3 | An agentic step resolves to "isolate": its own worktree unless a session is active | FR-8 without a second setting |
| AD-4 | FR-9's manifests are a `propose` verdict in `write_verdict`'s task branch: outside the task's files, `propose` instead of `strip` | one decider for grant and merge, as in `C-EXEC-08`; a `bash` step's listed manifest is untouched |

## ROI Analysis

### Investment Cost

Three sub-features: the policy, the agentic generate step, `sw implement`.

### Returns

A coder that can read and correct its own work in one step; the waiting `E-SENS-03` journey turns
green; `D-INTL-07` and `B-INTL-06` get a working dial.

### Risk Assessment

| Risk | Mitigation |
|---|---|
| An agent writes outside its task | the grant, the `[docs]` rules and the merge (NFR-4, FR-8) |
| A loop burns money | `[brake] agent_turns` and the spend limits (FR-4) |
| A model adds a dependency | FR-9: a proposal, never applied |

### Refactoring Opportunities

`AutonomySettings.max_turns` and the runtime's own loop go (AD-2); the unused "DAL unresolved"
branch stays as a guard only.

## Developer Guides Required

The user guide gains "Agentic steps": the settings above, what the coder may do, where its proposals
go.

## Non-Goals

- Agentic draft, review or plan steps: `D-INTL-07` extends the dial to drafting `[agreed 2026-10-19]`.
- Web search or plain file tools for the coder `[agreed 2026-10-19]`.
- Installing dependencies by the model `[agreed 2026-10-19]`.
- Multi-agent orchestration: `B-INTL-06`.
- A second `AgentRuntime`.

## Sub-Feature Breakdown

### SF-01: The project's policy

FR-1, FR-2, FR-6, FR-7. Input: `[autonomy]` and the pipeline. Output: each step's resolved mode, or a
refusal that names its cause.

### SF-02: An agentic generate step

FR-3, FR-4, FR-5, FR-8, FR-9. Input: a step resolved `agentic`. Output: the coder's files, through
the grant and the merge; manifest changes as proposals.

### SF-03: `sw implement` follows the dial

FR-10 `[agreed 2026-10-19]`. Input: the project's `[autonomy]`. Output: `sw implement`'s generate
steps agentic where allowed.

## Execution Order

SF-01, then SF-02, then SF-03.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | The project's policy | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | An agentic generate step | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | `sw implement` follows the dial | SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Now**: design approved 2026-10-20.
**Next**: the SF-03 plan (`sw implement` follows the dial). SF-02 committed 2026-10-20.
