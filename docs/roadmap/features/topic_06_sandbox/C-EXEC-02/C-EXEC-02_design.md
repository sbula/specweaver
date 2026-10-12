# C-EXEC-02 — Native CLI Action Nodes

**Status**: Built; `🔧` until the user signs off. · **Feature ID**: C-EXEC-02

| | |
|---|---|
| Builds on | `E-EXEC-01` (`SubprocessExecutor`) · `WorkspaceBoundary` (`sandbox/security.py`) |
| Enables | `B-EXEC-01` (container routing swaps the one `execute()` call) · `C-EXEC-04` (pre-merge scripts) |
| Uses | `TECH-011` — every step's `params` are checked when the pipeline loads |
| Not here | containers (`B-EXEC-01`), tiered access (`B-EXEC-02`), network egress (`E-EXEC-02`) |

## What it does

A pipeline step `action: bash, target: script` runs a script from the project's
`.specweaver/scripts/`. Its exit code, stdout and stderr land in the step's result, where gates,
routers and later steps read them. No model is involved. Typical use: installing dependencies or
seeding a database before code is generated or tests run.

```yaml
- name: seed
  action: bash
  target: script
  params: {script: seed.sh, args: ["--small"], timeout_seconds: 300}
```

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| AD-1 | `BashActionAtom` lives in `sandbox/execution/core/`; `sandbox/execution` itself keeps `forbids: core.flow.*` | the pattern of every domain `core.flow` uses; no rule weakened |
| AD-2 | The atom checks containment although atoms are trusted | the script name comes from pipeline YAML, which contributors edit |
| AD-3 | Containment reuses `WorkspaceBoundary`, not the role-grant system | one fixed folder; resolve before compare (CVE-2025-54794) |
| AD-4 | Later steps read results from `RunContext.step_records` | the runner already fills it; `feedback` stays for HITL notes |
| AD-5 | Always `bash`, found with `shutil.which`; no `.ps1`/`.bat` dispatch | the team runs Linux; a bare `bash` on Windows hits the WSL stub first |
| AD-6 | A script is a bare file name, resolved as `.specweaver/scripts/<name>` | no caller-supplied path to traverse |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Step type | Pipeline author | SHALL be able to declare `action: bash, target: script` with `params` `script`, `args`, `working_dir`, `timeout_seconds`, `env` | the pipeline loads |
| FR-2 | Containment | Loader, `BashActionAtom` | SHALL refuse at load a script name with a path separator or `..`, and before each run a script whose resolved path (symlinks followed) leaves `.specweaver/scripts/` `[agreed 2026-10-12]` | no script outside the folder runs |
| FR-3 | Fixed argv | `BashActionAtom` | SHALL run `[bash, <script>, *args]` without a shell, in `working_dir` resolved under the project (checked by `SubprocessExecutor`) | no shell injection from names, args or earlier output |
| FR-4 | Structured result | `BashActionAtom` | SHALL put `exit_code`, `stdout`, `stderr`, `duration_seconds` and `timed_out` in the step's output | later steps read fields, not a last line of stdout |
| FR-5 | Status | `BashActionAtom`, handler | SHALL pass a step that exits 0 and fail any other exit or a timeout; a script that never ran is ERROR | gates and routers work unchanged |
| FR-6 | Later steps | Runner | SHALL keep the step's output in `RunContext.step_records` for every later step | no new state channel |
| FR-7 | Routing | `RouterRule` | SHALL route on `output.exit_code` and `output.stdout` | branching with the existing router |
| FR-8 | Output cap | `BashActionAtom` | SHALL cut each of stdout and stderr to 1 MiB and mark the cut `...[TRUNCATED]` | stored run state stays bounded |
| FR-9 | Timeout | Pipeline author, atom | SHALL let a step set `timeout_seconds` (default 120, at most 3600, else refused at load), and say "timed out after N s" when it is hit | a hung script ends, and says why |
| FR-10 | Scaffold | `sw init` | SHALL create `.specweaver/scripts/` with a `README.md` on the containment rule | the folder exists in every project |
| FR-11 | Limits | `BashActionAtom` | SHALL run every script under 2 GiB of memory (`RLIMIT_AS`) and a process ceiling: the tasks the user already runs plus the larger of 128 and 1% of the system's hard `RLIMIT_NPROC`, at most that hard limit | a runaway or forking script is capped; on Linux the ceiling is per user, not per script (`B-EXEC-04` makes it per subtree) |
| FR-12 | Env | `BashActionAtom` | SHALL pass only the step's own `env` map, never the run's variables, and refuse at load a `PATH` key in any case | no secret leaks into output; no step picks its own bash |
| FR-13 | Contained failure | atom, handler | SHALL turn every exception of a bash step into that step's ERROR with a readable message | one step fails, not the run |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Canonical containment | compare resolved paths, never string prefixes; any resolution failure refuses |
| NFR-2 | No shell | always an argv list; never a command string built from names, args or output |
| NFR-3 | Credentials | the shell's provider keys (`GEMINI_API_KEY`, ...) never reach a script (`SubprocessExecutor`'s stripping) |
| NFR-4 | Timeout | default 120 s, at most 3600 s |
| NFR-5 | Output cap | 1 MiB per stream |
| NFR-8 | Observability | one DEBUG line per run: command (script and args), folder, timeout, exit code, duration |
| NFR-9 | Clear errors | a missing script, a containment breach, no `bash` on `PATH`, and a timeout each have their own message |
| NFR-10 | Compatibility | every other step type behaves as before |

## Accepted limits

- A script swapped between the pre-run check and the start is not caught; it needs write access to
  `.specweaver/scripts/`, which agents do not have.
- After a router jump the following steps still run in order; there is no end-of-run target.
- On Windows with WSL's `bash.exe`, Windows paths in `args` are not translated.

## Live demo

`sw init`, then `greet.sh` in `.specweaver/scripts/`: `sw run p.yaml spec.md` with a bash step
passes on exit 0 and fails on exit 3, naming the stderr line; a router sends exit 0 and exit 3 to
different steps; `timeout_seconds: 1` on a `sleep 5` script says "timed out after 1 s"; `../x.sh`,
`env: {Path: /tmp}` and `script:` beside `params:` are refused before any step runs.
`tests/e2e/capabilities/sandbox/test_bash_step_journey_e2e.py` does exactly this.

## Sub-features

| SF | Does | FRs | Plan |
|----|------|-----|------|
| SF-01 | `BashActionAtom` | FR-2, FR-3, FR-4, FR-8, FR-9, FR-11, FR-12, FR-13 | [sf01](C-EXEC-02_sf01_implementation_plan.md) |
| SF-02 | Step type, handler, routing | FR-1, FR-5, FR-6, FR-7 | [sf02](C-EXEC-02_sf02_implementation_plan.md) |
| SF-03 | Scaffold, module boundaries, guides | FR-10 | [sf03](C-EXEC-02_sf03_implementation_plan.md) |
