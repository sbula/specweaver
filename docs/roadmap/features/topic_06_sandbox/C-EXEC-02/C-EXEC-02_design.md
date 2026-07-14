# Design: Native CLI Action Nodes

- **Feature ID**: C-EXEC-02
- **Phase**: Design
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_design.md

## Feature Overview

Feature C-EXEC-02 adds a declarative `action: bash` pipeline step (a "Native CLI Action Node") to SpecWeaver's YAML pipeline engine. It solves the problem of needing deterministic, non-LLM shell steps inside a pipeline — e.g. pre-test scaffolding, dependency installs, DB seeding — by letting a pipeline author declare a `bash` step that invokes a script from a fixed, protected directory and captures its `stdout`/`stderr`/`exit_code` into pipeline state, without routing the step through an LLM agent. It interacts with `core/flow` (pipeline engine models/handlers), a new `sandbox/execution/core` Atom (wrapping the existing `SubprocessExecutor` from E-EXEC-01), and the existing `FolderGrant`/`WorkspaceBoundary` security primitives in `sandbox/security.py`. It does NOT touch containerized execution (`B-EXEC-01`), tiered access rights (`B-EXEC-02`), or air-gapped network egress control (`E-EXEC-02`) — those remain separate, later features. Key constraint: every referenced script MUST physically resolve inside `.specweaver/scripts/` (canonical-path containment, to prevent Agent RCE); execution MUST go through `SubprocessExecutor`, never raw `subprocess`.

## Research Findings

### Codebase Patterns

**Pipeline engine (`core/flow/`)**: `PipelineStep` = `action: StepAction` + `target: StepTarget`, both closed `StrEnum`s validated against a `VALID_STEP_COMBINATIONS` allowlist in `PipelineDefinition.validate_flow()`. Adding `bash` requires a new `StepAction.BASH` value + a new combination entry — the same mechanism already used for every existing step type (`generate`, `validate`, `review`, `draft`, `arbitrate`, `orchestrate`). `StepHandlerRegistry` (`handlers/registry.py`) is a plain `dict[(StepAction, StepTarget), StepHandler]`; `StepHandler` is a `Protocol` with one method: `async def execute(step, context) -> StepResult`. `GateDefinition`/`RouterRule` operate purely on `StepResult.output` (dot-notation, no `eval()`) — a bash step needs zero gate/router changes to become failable and routable, it just needs to populate `output` and map exit code → `StepStatus`.

**Downstream state — no new plumbing needed.** `RunContext.step_records: list[dict[str, Any]]` is refreshed by `runner.py` (`self._context.step_records = [r.model_dump() for r in run.step_records]`) immediately before *every* step executes, and contains every prior `StepRecord` (`step_name`, `status`, `result: StepResult`) for the whole run. Any handler — including ones after a bash step — can already read a named prior step's `result.output` from `context.step_records`. This is distinct from `RunContext.feedback`, which is reserved for HITL loop-back rejection notes (`inject_feedback`, rendered as `<dictator-overrides>` per C-FLOW-05) and only fires on loop-back. C-EXEC-02 reuses `step_records`, not `feedback`.

**SubprocessExecutor (`sandbox/execution/executor.py`, from E-EXEC-01, complete)**: `execute(cmd: list[str], *, timeout_seconds=None, extra_env=None, cwd_override=None, input_text=None) -> SubprocessResult(exit_code, stdout, stderr, duration_seconds, timed_out, events)`. Already provides: SIGTERM→2s-grace→SIGKILL timeout escalation (Windows: immediate `terminate()`), env allowlisting + hard credential stripping (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AZURE_*`, ...), and canonical-path `cwd` validation (`_validate_cwd`, resolves symlinks, checks `relative_to(boundary)`). Direct quote from the E-EXEC-01 design doc's own Returns table: *"C-EXEC-02 Native CLI Nodes | Needs safe `bash` execution from YAML | Directly uses SubprocessExecutor"* — E-EXEC-01 is complete (2026-07-12) specifically to unblock this feature.

**Direct usage of `subprocess.run()` is banned repo-wide via ruff rule TID251**, exempted only for `sandbox/execution/` itself and test files (`docs/dev_guides/subprocess_execution.md`). C-EXEC-02's new code must call `SubprocessExecutor.execute()`, never `subprocess` directly.

**Security (`sandbox/security.py`)**: `WorkspaceBoundary.validate_path(requested: Path) -> Path` resolves symlinks and checks subpath containment against configured roots, raising on escape — this is the canonical-path-containment primitive to reuse for `.specweaver/scripts/`. Separately, `FolderGrant`/`AccessMode`/`_compute_role_grants` (`sandbox/dispatcher.py`) is a *dynamic, per-role* grant system used exclusively to gate agent-facing `Tool` calls — it has no "is this path inside a single fixed folder" utility as a standalone function; that logic is embedded as a private method (`FileSystemTool._check_grant`) on the Tool class. `.specweaver/scripts/` is a single static boundary, not a per-role dynamic grant, so C-EXEC-02 uses `WorkspaceBoundary`-style containment directly rather than the role-grant machinery (see AD-3). Also confirmed: `FileExecutor._PROTECTED_PATTERNS` (the agent-facing filesystem executor) already includes `.specweaver` as a protected pattern — LLM agents physically cannot write/move/delete anything under `.specweaver/` today via `FileSystemTool`. This is a pre-existing, already-true structural guarantee that scripts in `.specweaver/scripts/` can only be authored by a human or CLI scaffolding, reinforcing the RCE-prevention mandate without new code.

**Tool vs. Atom (`docs/dev_guides/adding_tools_and_atoms.md`, `docs/architecture/01_foundational_principles/atoms_vs_tools.md`)**: two parallel stacks — `Tool` (agent-facing, role/grant-gated) vs. `Atom` (engine-facing, triggered by the flow engine, normally bypasses grants because "the engine is trusted"). Since a bash step is explicitly "triggered by the pipeline runner, never exposed to an LLM's function-calling surface," it is unambiguously **Atom-tier**, mirroring `QARunnerAtom`/`GitAtom`. `QARunnerAtom._intent_run_tests` already performs a path-traversal check (`is_relative_to`) despite being an Atom — direct precedent that an Atom performing an explicit containment check on a YAML-sourced path is normal, not a deviation from the trust model (see AD-2).

**Module boundary gap (a real contradiction to resolve, not a switch — see AD-1)**: `sandbox/execution/context.yaml` currently declares `forbids: [sandbox.qa_runner.*, core.flow.*]`, and `tach.toml`'s `[[interfaces]] from=["specweaver.sandbox"]` expose-list does not list `execution` at all — `core.flow` has no sanctioned import path to `SubprocessExecutor` today. Every other domain flow legitimately consumes (`qa_runner`, `git`, `code_structure`, `mcp`) does so through a `<domain>/core` submodule with its own `context.yaml`, distinct from that domain's execution/interfaces internals. `sandbox/execution/` currently has no `core/` submodule (flat: `executor.py`, `models.py`, `platform_limiter.py`, `_signals.py`). AD-1 proposes adding `sandbox/execution/core/` for the new Atom, following this exact existing precedent.

**Scaffolding**: `workspace/project/scaffold.py` creates `.specweaver/`, `.specweaver/templates/`, `.specweaver/vault.env` — no `scripts/` subdirectory exists yet.

**Example pipelines** (`workflows/pipelines/new_feature.yaml`, `scenario_integration.yaml`) confirm the engine already cleanly separates deterministic steps (`action: validate`, dispatched to `QARunnerAtom`, no LLM involved) from LLM-driven steps (`action: generate/draft/review`) — but there is currently no step type for arbitrary deterministic setup/scaffolding (e.g. `pip install -e .`, DB seed, `npm ci`) before `generate_code` or `run_tests`. Today that gap is either handled outside the pipeline entirely or folded into an LLM step's instructions — exactly the gap this feature closes.

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| `SubprocessExecutor` (internal, E-EXEC-01) | current | `.execute(cmd, timeout_seconds, extra_env, cwd_override, input_text)` | `src/specweaver/sandbox/execution/executor.py` |
| `WorkspaceBoundary` (internal) | current | `.validate_path(requested) -> Path` | `src/specweaver/sandbox/security.py` |
| `bash` (WSL/Git Bash on Windows; native on Linux/macOS) | any POSIX-compatible | invoked as `["bash", script_path, *args]` | host PATH |

No new third-party dependencies. This feature is a pure composition of existing internal primitives.

### Blueprint References

`docs/ORIGINS.md` credits this feature to Archon (github.com/coleam00/Archon), an open-source AI-coding harness using YAML DAGs + git worktrees, citing "Native CLI Action Nodes" / `action: bash` / "FolderGrant" as adopted patterns (Phase 3.40b). **Verified against the actual Archon source during this design's research**: Archon does have a real, analogous bash/script DAG-node pattern (`packages/workflows/src/schemas/dag-node.ts` — `bashNodeSchema` with a `bash: string` field and `timeout` default 120000ms, output exposed to downstream nodes as `$nodeId.output`, with a documented "don't double-quote `$node.output`" shell-injection footgun) and genuine canonical-path/symlink defenses in its worktree provider — but the specific terms **"Native CLI Action Nodes," `action:` as a discriminator key, and "FolderGrant" do not exist in Archon's codebase or docs**. They are SpecWeaver's own coinage, inspired by Archon's bash-node *concept*, not borrowed Archon terminology. `ORIGINS.md`'s attribution is imprecise on this point (worth a follow-up doc fix — see Refactoring Opportunities) but does not block this design.

External prior art incorporated into the FRs/NFRs below: GitHub Actions' `GITHUB_OUTPUT` injection-risk guidance (never re-interpolate captured output into a subsequent shell command unescaped → FR-3), Airflow `BashOperator`'s "implicit last-stdout-line XCom" fragility (→ FR-4 explicit structured capture instead of magic parsing), and CVE-2025-54794 (Claude Code path-restriction bypass via prefix-matching instead of canonical-path comparison) plus the general symlink-escape lesson (→ FR-2, AD-3: must resolve() before containment check, never string-prefix compare).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | New step type | Pipeline author | Declares a step with `action: bash`, `script: <name>`, optional `args: [...]` and `working_dir: <relative-path>` in pipeline YAML | `PipelineDefinition.validate_flow()` accepts the new `(StepAction.BASH, StepTarget.SCRIPT)` combination |
| FR-2 | Script path containment | System | Resolves `script: <name>` strictly as `<project_path>/.specweaver/scripts/<name>` (rejecting any `name` containing a path separator or `..`), then canonically validates (post symlink-resolution, via `WorkspaceBoundary`-style check) that the resolved path is a descendant of `.specweaver/scripts/` — performed **both** at pipeline-load validation time (fast author feedback) **and again, atomically, immediately before every execution** inside `BashActionAtom` itself | Any escape attempt — traversal, symlink, absolute-path override, or a script swapped in between an earlier pipeline-load check and a much-later execution (e.g. across a long HITL pause) — hard-fails, never a warning |
| FR-3 | Deterministic invocation | `BashActionAtom` | Invokes the validated script via `SubprocessExecutor.execute(["bash", resolved_path, *args], cwd_override=<working_dir resolved relative to project_path>, ...)` — fixed argv, `shell=False` always, never interpolates a prior step's captured output into the command string. `working_dir` (if set) is resolved relative to `project_path` (not `.specweaver/scripts/`) and its containment is enforced by `SubprocessExecutor`'s existing `_validate_cwd` boundary check — no separate validation is written | No shell-injection surface from either the script path, `working_dir`, or upstream pipeline state |
| FR-4 | Structured capture | `BashActionAtom` | Captures `exit_code`, `stdout`, `stderr`, and `duration_seconds` into `StepResult.output` | Downstream consumers get typed fields, never an implicit "last line of stdout" convention |
| FR-5 | Status mapping | `BashActionHandler` | Maps exit code 0 → `StepStatus.PASSED`¹, any nonzero → `StepStatus.FAILED` | Existing `GateDefinition`/`RouterRule` evaluation works on bash steps with zero engine changes |
| FR-6 | Downstream availability | System | Makes a completed bash step's `StepResult.output` readable by every later step in the same run via the existing `RunContext.step_records` list (keyed by `step_name`) | No new state-propagation channel; later handlers read `context.step_records` exactly as the runner already provides it |
| FR-7 | Router compatibility | `RouterRule` | Supports dot-notation branching on a bash step's `output.exit_code` and `output.stdout` (raw string) | Pipeline authors can branch on bash-step results using the existing router with no new syntax. **Deferred (not built now)**: best-effort structured/JSON parsing of `stdout` into a typed field — cut from MVP scope as speculative (YAGNI); revisit only if a concrete pipeline author need emerges |
| FR-8 | Output truncation | `BashActionAtom` | Truncates each of `stdout`/`stderr` to 1 MiB, appending a `...[TRUNCATED]` marker when truncation occurs, before storing in `StepResult.output` | Bounds `step_records` JSON payload size (persisted to SQLite) and prevents unbounded memory growth from a runaway script |
| FR-9 | Timeout override | Pipeline author | May set `timeout_seconds` on a bash step in YAML | If set, overrides the `SubprocessExecutor` default (120s) for that step only; if omitted, the default applies unchanged |
| FR-10 | Scaffold | `sw init` / project scaffold | Creates `.specweaver/scripts/` (with a placeholder `README.md` explaining the containment rule) as part of project scaffolding | The grant target directory always exists once a project is initialized; no separate manual setup step |
| FR-11 | Default resource limits | `BashActionAtom` | Constructs `SubprocessExecutor` with non-`None` default `ResourceLimits`: `max_memory_bytes=2_147_483_648` (2 GiB), `max_processes=128`, for every bash step invocation | A runaway or fork-bombing script is capped by default; pipeline authors may tune within a bounded range but MAY NOT disable limits entirely. *(Forward-compat note: if/when a DAL-aware default-limits system lands in `SubprocessExecutor` itself, `BashActionAtom` should adopt it instead of these feature-local hardcoded defaults.)* |
| FR-12 | Explicit env opt-in | `BashActionAtom` | Does **NOT** implicitly pass `RunContext.env_vars` into the bash script's environment. A pipeline author MAY declare an explicit `env: {KEY: value}` map on the step; each key is passed as `extra_env` to `SubprocessExecutor.execute()` (which already unconditionally strips credential vars per E-EXEC-01 AD-4). Any key matching `PATH` case-insensitively (`PATH`, `Path`, `path`, ...) in the step's `env:` map is rejected at pipeline-validation time | Prevents silent secret leakage from `RunContext.env_vars` into `stdout`/`step_records`/SQLite, and prevents a step from hijacking which `bash` executable resolves via a `PATH` override |
| FR-13 | Exception containment | `BashActionAtom` / `BashActionHandler` | Catches every exception raised during containment validation, `working_dir` resolution, or `SubprocessExecutor` execution, and converts it into a `StepResult` with `StepStatus.ERROR` and a human-readable `error_message` (using the existing `_error_result` helper pattern from `handlers/base.py`) | No exception from a bash step may propagate unhandled and crash the pipeline run; only that one step fails |

¹ *Corrected during SF-2 implementation (2026-07-14): `StepStatus` has no `COMPLETED` member. The actual mapping uses `StepStatus.PASSED`, consistent with every other handler in `core/flow/handlers/`. See the SF-2 implementation plan's Research Notes.*

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|------------------------|
| NFR-1 | Security — path containment | MUST use canonical (post-`resolve()`) path comparison, never string-prefix matching (CVE-2025-54794 lesson). MUST reject on any resolution failure (fail closed, not open). Zero tolerance: any script path resolving outside `.specweaver/scripts/` MUST abort pipeline validation, not merely log a warning. |
| NFR-2 | Security — no shell interpolation | MUST always invoke via argv list (`shell=False`); MUST NOT build a shell string by concatenating script path, args, or any prior step's captured output. |
| NFR-3 | Security — credential isolation | Inherits `SubprocessExecutor`'s existing env allowlist + credential-stripping (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AZURE_*`, ...) unchanged — no new env var exposed to bash scripts beyond the existing allowlist. |
| NFR-4 | Performance — default timeout | 120s (inherited from `SubprocessExecutor` default), author-overridable per step (FR-9) up to a hard ceiling of 3600s (1 hour); values above the ceiling are rejected at pipeline-validation time. |
| NFR-5 | Performance — output cap | 1 MiB per stream (stdout/stderr independently), per FR-8. |
| NFR-6 | Compatibility — interpreter | `bash` is invoked literally (`["bash", ...]`) on all platforms. On Windows this resolves via WSL's `bash.exe` or Git Bash if present on PATH — no OS-appropriate interpreter dispatch (`.ps1`/`.bat`) is built. If `bash` is not resolvable on PATH, the step fails immediately with a clear "bash interpreter not found on PATH" error message (not a silent skip or a different-interpreter fallback). **Known limitation (accepted, transitional)**: when `bash` resolves to WSL's `bash.exe`, Python-resolved Windows-style paths (`C:\...`) passed as the script path, `working_dir`, or path-valued `args` are NOT automatically translated to WSL mount-point form (`/mnt/c/...`) — WSL only translates its own leading executable argument, not embedded path arguments. Git Bash, by contrast, accepts native Windows paths directly. This is not solved by this design; it is accepted given the user-confirmed imminent migration to native Ubuntu (see project memory). Script authors targeting a Windows+WSL host are responsible for path-safe scripting (e.g. `wslpath`) or preferring Git Bash on PATH. |
| NFR-7 | Compatibility — Python/OS | Same targets as E-EXEC-01: Python 3.11+, Windows 11 (26H2+) via WSL/Git Bash, Linux (kernel 7.1+), macOS Tahoe (26+) — all via existing `SubprocessExecutor` cross-platform support, no new OS-specific code. |
| NFR-8 | Observability | Every bash step execution logged at DEBUG level with: script name, resolved path, args, cwd, timeout, exit_code, duration — consistent with `SubprocessExecutor`'s existing NFR-5 (E-EXEC-01) logging convention. |
| NFR-9 | Error handling | A missing script file, a containment violation, or `bash` not found on PATH all raise distinct, human-readable error messages (not a generic `FileNotFoundError` traceback) surfaced in `StepResult.error_message`. |
| NFR-10 | Backward compatibility | Zero changes to any existing `StepAction`/`StepTarget` combination's behavior. All existing pipeline YAML files continue to validate and run unchanged. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| `SubprocessExecutor` (internal) | current (E-EXEC-01, complete) | `.execute()` | ✅ | No changes needed to E-EXEC-01 itself |
| `WorkspaceBoundary` (internal) | current | `.validate_path()` | ✅ | Reused as-is for containment check |
| `bash` | any POSIX-compatible (WSL/Git Bash on Windows) | invoked via argv, no bash-version-specific features required | ✅ (user-confirmed WSL installed; team migrating to Ubuntu within weeks) | No new dependency installation required by SpecWeaver itself — `bash` is assumed present on the host |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | New `BashActionAtom` lives in a new `sandbox/execution/core/` submodule (its own `context.yaml`, `archetype: adapter`, `consumes: [sandbox.execution]`), while the existing `sandbox/execution/context.yaml` (root — `executor.py` itself) keeps its `forbids: core.flow.*` unchanged | Resolves the real contradiction found in research (`sandbox/execution` currently forbids `core.flow.*`, and `tach.toml` doesn't expose `execution` to outside consumers) **without weakening any existing rule** — it mirrors the exact precedent already used by every domain `core.flow` legitimately consumes (`qa_runner/core`, `git/core`, `code_structure/core`, `mcp/core`), each of which has its own `context.yaml` distinct from sibling internals. It is also directly compliant with the authoritative layering rule in `src/specweaver/sandbox/CLAUDE.md`: "An atom may import from commons. Never from tools." — the new `execution/core` Atom importing the existing `execution` module (a `commons`-tier leaf per that same doc's description, despite `CLAUDE.md`'s illustrative commons list predating this module) is exactly "atom → commons," not a new pattern. Additive, precedent-following, not a rule violation. | No |
| AD-2 | `BashActionAtom` performs an explicit canonical-path containment check even though Atoms normally bypass `FolderGrant`/role checks ("the engine is trusted") | The script *path* originates from pipeline YAML, which is contributor-editable/version-controlled content — not purely engine-internal state. Direct precedent: `QARunnerAtom._intent_run_tests` already performs a path-traversal check (`is_relative_to`) despite being an Atom. This is consistent with existing Atom practice, not a new trust-model exception. | No |
| AD-3 | Containment check **literally instantiates and reuses** `sandbox.security.WorkspaceBoundary` (e.g. `WorkspaceBoundary(roots=[project_path / ".specweaver/scripts"]).validate_path(resolved)`) — no reimplementation of resolve/subpath logic — and does NOT use the dynamic `FolderGrant`/`_compute_role_grants` role-based system | `.specweaver/scripts/` is a single fixed boundary, not a dynamic multi-role grant list — routing it through the dynamic grant machinery (`ToolDispatcher._compute_role_grants`, designed for per-agent-role Tool access) would be over-engineering a static, single-purpose check. Reusing the class directly (not a lookalike reimplementation) avoids a DRY violation and inherits its resolve-before-compare behavior (CVE-2025-54794 lesson: prefix-string matching is bypassable; symlinks must be resolved before containment check, not after). Per FR-2, this call happens both at load-time validation and again immediately before each execution. | No |
| AD-4 | Downstream state propagation reuses the existing `RunContext.step_records` mechanism (already refreshed by the runner before every step) — no changes to `runner.py`, no repurposing of `RunContext.feedback`/`inject_feedback` | `step_records` already carries every prior step's full `StepResult` to every subsequent handler with zero new plumbing. `feedback` is semantically reserved for HITL loop-back rejection notes (`<dictator-overrides>`, C-FLOW-05) and only fires on loop-back — conflating the two would blur an established, load-bearing convention. | No |
| AD-5 | `bash` interpreter invocation is literal (`["bash", script_path, *args]`) on all platforms; no OS-appropriate interpreter dispatch (`.ps1`/`.bat`) is built | User-confirmed: WSL is installed today (bash already resolvable on PATH) and the team is migrating the whole environment to Ubuntu within weeks — building Windows-native dispatch logic now would be near-immediate dead weight. Fails fast with a clear error if `bash` isn't found, rather than silently degrading. | No — scoping decision, confirmed with user during Phase 3 clarification |
| AD-6 | Scripts are referenced by bare name only (`script: setup.sh`), resolved as `.specweaver/scripts/<name>` — never a caller-supplied path or absolute path | Closes the path-traversal surface by construction (FR-2's rejection of separators/`..` is defense-in-depth on top of this, not the only line of defense) and matches Archon's own `script: analyze-metrics` → `.archon/scripts/analyze-metrics.py` named-reference convention (verified against actual Archon source). | No |

## ROI Analysis

### Investment Cost

| Item | Effort | Risk |
|------|--------|------|
| `BashActionAtom` + containment check + unit tests (SF-1) | ~150 lines | Low — pure composition of existing, tested primitives |
| `StepAction.BASH` + `BashActionHandler` + registry wiring + integration tests (SF-2) | ~120 lines | Low — well-trodden step-type extension mechanism |
| Scaffold + `tach.toml`/`context.yaml` edits + dev-guide updates (SF-3) | ~40 lines + doc edits | Low |
| **Total** | **~310 lines new** | **Low overall** |

### Returns

| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| Pipeline authors (`new_feature.yaml`, `scenario_integration.yaml`, future pipelines) | Can insert deterministic setup/scaffolding (dependency install, DB seed, format-fix) before `generate_code`/`run_tests` without spending LLM tokens or introducing nondeterminism | **Closes a real, currently-unfilled gap** (confirmed: no existing step type covers this) |
| `B-EXEC-01` (Ephemeral Podman Sub-Containers) | `BashActionAtom`'s single `SubprocessExecutor.execute()` call site is exactly the swap point a container-routing feature needs | **Architecture enabler**, same pattern E-EXEC-01 already set up for QARunner |
| `C-EXEC-04` (Concurrent Git Merge Orchestration) | Could use bash nodes for deterministic pre-merge validation scripts | **Future unlock** |
| Security posture | Closes the "no way to run deterministic shell without going through an LLM tool call or manual dev action" gap with a hard-contained, auditable primitive | **Immediate hardening** |

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Author accidentally captures secrets via a bash script's own logic (e.g. `env` dump) despite env stripping | Low | Medium | `SubprocessExecutor`'s existing allowlist + credential-stripping already limits what's in the child env in the first place; document the risk in the dev guide |
| Truncation silently drops a downstream router's expected JSON field | Low | Low | 1 MiB cap is generous for structured status output; `[TRUNCATED]` marker makes truncation visible in logs/output rather than silent |
| `bash` not present on a given Windows host | Medium (until Ubuntu migration completes) | Low | Fails fast with a clear, actionable error (NFR-9) rather than a confusing subprocess traceback |
| WSL-invoked `bash` misinterprets Windows-style paths in `args`/`working_dir` | Medium (until Ubuntu migration completes) | Medium (script fails with a confusing "no such file" rather than a clear path-translation error) | Accepted transitional limitation (NFR-6) — not fixed by this design given the imminent Ubuntu migration; documented so it's not mistaken for a bug |
| Residual TOCTOU window between FR-2's pre-execution re-validation and the actual `SubprocessExecutor.execute()` call | Very Low (requires filesystem write access to `.specweaver/scripts/`, which is already git-tracked and blocked from LLM-agent writes) | Medium | Accepted risk — narrowed from "hours across a HITL pause" to "microseconds within one function call" (industry-standard mitigation per CVE-2025-54794 remediation guidance); a fully atomic fix would need OS-level open-by-fd primitives disproportionate to this feature's threat model |
| Hardcoded resource-limit defaults (FR-11) diverge from a future DAL-aware limits system | Low | Low | Accepted, flagged as a forward-compat note in FR-11 — migrate `BashActionAtom` to a DAL-aware default if/when `SubprocessExecutor` gains one |

### Refactoring Opportunities

| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `docs/ORIGINS.md` Archon section | Attributes "Native CLI Action Nodes," `action: bash`, and "FolderGrant" to Archon as if they were Archon's own terminology; verified against the actual Archon source they are not — Archon uses `bash:`/`script:` node fields and has no "FolderGrant" concept | Correct the attribution to "inspired by Archon's bash/script DAG-node pattern" without implying the terms are borrowed | Trivial (doc-only) |
| `docs/architecture/03_system_topology/hard_dependency_rules.md` | Already stale before this feature — lists `flow`'s consumes set incorrectly (missing `git/core`, `code_structure/core`, `mcp/core`, which are already live) | This feature's `context.yaml` edits (AD-1) are the natural trigger to bring this doc back in sync, adding the new `execution/core` entry at the same time | Small (doc-only) |
| `sandbox/filesystem/interfaces/models.py` | Duplicate `FolderGrant`/`AccessMode`/`MODE_ALLOWS_*` definitions exist here, separate from the canonical copy in `sandbox/security.py` that's actually imported and used | Not touched by C-EXEC-02 (AD-3 avoids the grant system entirely), but flagged here so a future cleanup doesn't get missed — out of scope for this feature | N/A — informational only, no action taken in C-EXEC-02 |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Guide-1 | New numbered section in `docs/dev_guides/pipeline_engine_guide.md` covering `action: bash` steps — how to declare one, the `.specweaver/scripts/` containment rule, output shape, and how downstream steps read `context.step_records` | ⬜ Deferred to SF-2's pre-commit gate — `action: bash` isn't a working pipeline step until SF-2 lands; documenting it now would describe a capability that doesn't exist yet |
| Guide-2 | Note in `docs/dev_guides/subprocess_execution.md` cross-referencing the new `BashActionAtom` as the sanctioned way to run a script from a pipeline step | ✅ Written in SF-1's pre-commit (2026-07-13) |

## Sub-Feature Breakdown

### SF-1: BashActionAtom Core Execution
- **Scope**: Build the `BashActionAtom` (in a new `sandbox/execution/core/` submodule) that validates script-path containment (at load-time and again pre-execution), invokes `SubprocessExecutor` with default resource limits and explicit env opt-in, truncates output, catches all exceptions, and returns a structured `AtomResult`. Fully testable in isolation with fixture scripts — no pipeline engine involvement yet.
- **FRs**: [FR-2, FR-3, FR-4, FR-8, FR-9, FR-11, FR-12, FR-13] *(8 FRs — exceeds the usual ≤5 agent-sized heuristic; deliberately kept together rather than split, since FR-11/12/13 were added by the Red/Blue review as hardening constraints on the same single `execute()` call FR-3 already makes on the same class — they are not independently valuable or testable per the Phase 4.3 self-containment rule, so splitting them into a separate SF would add coordination overhead with no real parallelism benefit)*
- **Inputs**: script name, args, working_dir, timeout_seconds, project_path (from caller — a unit test harness in this SF, the pipeline handler in SF-2)
- **Outputs**: `AtomResult(status, exports={exit_code, stdout, stderr, duration_seconds})`
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_sf1_implementation_plan.md

### SF-2: Pipeline Engine Integration
- **Scope**: Add `StepAction.BASH`/`StepTarget.SCRIPT` to the pipeline models, register `BashActionHandler` (wraps SF-1's Atom, maps exit code → `StepStatus`), and confirm `RouterRule`/`GateDefinition`/`step_records` propagation work end-to-end via integration tests using real pipeline YAML.
- **FRs**: [FR-1, FR-5, FR-6, FR-7]
- **Inputs**: `BashActionAtom` from SF-1, existing `PipelineStep`/`StepHandlerRegistry`/`RunContext` machinery
- **Outputs**: A pipeline YAML file with an `action: bash` step runs end-to-end, is routable, and its output is readable by later steps
- **Depends on**: SF-1, SF-3 *(code depends only on SF-1's `BashActionAtom`; SF-3's `tach.toml`/`context.yaml` edits are additionally required for this SF's imports to pass `tach check` — not a code dependency on SF-3's FR-10 scaffold/docs work itself)*
- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_sf2_implementation_plan.md

### SF-3: Scaffold, Boundary Config, and Docs
- **Scope**: Extend `workspace/project/scaffold.py` to create `.specweaver/scripts/` on project init; add `sandbox/execution/core` to `tach.toml`'s sandbox interface expose-list and to `core/flow/context.yaml`'s `consumes`; correct `hard_dependency_rules.md` and `ORIGINS.md`'s Archon attribution; write the dev-guide sections.
- **FRs**: [FR-10]
- **Inputs**: none (parallelizable — does not require SF-1/SF-2 code, only the module *names* they will introduce)
- **Outputs**: `.specweaver/scripts/` exists on every newly-scaffolded project; `tach check` passes once SF-1/SF-2 land; docs are accurate
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_sf3_implementation_plan.md

## Execution Order

1. **SF-1** and **SF-3** in parallel (both have no dependencies — SF-1 builds the execution primitive, SF-3 prepares scaffolding/boundary config independently).
2. **SF-2** (depends on **both** SF-1 and SF-3): wires the primitive into the pipeline engine. Requires SF-1's `BashActionAtom` to exist (code dependency) AND SF-3's `tach.toml`/`context.yaml` edits to exist (config dependency, so `sandbox/execution/core` is a tach-legal import for `core/flow`) before it can pass `tach check`.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | BashActionAtom Core Execution | — | ✅ | ✅ | ✅ | ✅ | ⬜ |
| SF-2 | Pipeline Engine Integration | SF-1, SF-3 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-3 | Scaffold, Boundary Config, and Docs | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status** (2026-07-14): Design APPROVED. SF-1 and SF-3 are fully implemented, tested, and committed. SF-2 (Pipeline Engine Integration)'s implementation plan is APPROVED; SF-2 TDD development in progress via the `dev` skill.

**Notable finding during SF-1's TDD (Task T6)**: `SubprocessExecutor.execute(["bash", ...])` with the bare string `"bash"` resolved to WSL's `bash.exe` stub in `C:\Windows\System32` instead of Git Bash, because Windows' `CreateProcess` default search order checks `System32` before `%PATH%` regardless of PATH order. Fixed by resolving `shutil.which("bash")` once per `run()` call and using the returned absolute path as argv[0]. This is now baked into `BashActionAtom`'s implementation; SF-2/SF-3 don't need to account for it further.

**Side effect of SF-1's pre-commit gate**: repo-wide `ruff check` (mandated by the pre-commit skill, "every error MUST be fixed regardless of pre-existing or newly introduced") surfaced 6 pre-existing `TID251` violations unrelated to C-EXEC-02. Resolved: `git/core/executor.py` and `filesystem/core/search.py` were migrated to `SubprocessExecutor` via constructor/parameter DI, implementing the already-designed **TECH-009** (previously design-complete but unimplemented) — see `docs/roadmap/features/topic_07_technical_debt/TECH-009/TECH-009_design.md`. `cli_drift.py` and `assurance/standards/discovery.py` kept raw `subprocess` with documented `noqa: TID251` exemptions (routing them through `sandbox` would cross a bounded-context line that doesn't exist today — a real architecture decision, deferred to TECH-009's backlog). `mcp/core/executor.py` also kept a documented exemption — its persistent, bidirectional subprocess pattern is architecturally incompatible with `SubprocessExecutor.execute()`'s one-shot design; tracked as new ticket **TECH-010**. A `C901` complexity violation in `tests/unit/test_architecture.py` (unrelated) was also fixed. None of this touched C-EXEC-02's own scope.

**Next step**: Complete SF-2 dev + pre-commit + commit. Once done, C-EXEC-02 is feature-complete.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate skill.
