# Design: Each Entry Point Builds Its Run by Hand, and the API Gets Less

- **Feature ID**: TECH-077
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 16 below.

## Problem Statement

About ten entry points build a run's context by hand and each leaves different parts out. API runs
get no constitution, no standards and no `[docs]`/`[autonomy]` policy; `sw resume` uses the current
folder's project.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **Fix first #4** — A run's context (constitution, standards, isolation, DAL escalation, settings)
  is built by hand in about 10 places; API runs get no constitution, no standards and no
  `[docs]`/`[autonomy]` policy. Where: `core/flow/interfaces/cli.py:245`,
  `interfaces/api/v1/pipelines.py:57`, `_llm.py:146`, review/implement/drift CLIs.
- **FL-8** — `RunContext` built by hand at every entry point. Where: 10 sites (Fix first #4).
- **FL-12** — The archetype is found three ways (root file only, nearest file, topology). Where:
  `run_context.py:244`, `archetype_pipelines.py:41`, `context_assembler.py:47`.
- **FL-20** — "Registered project lookup with fallback" four times. Where: `naming.py:17`,
  `scenario_store.py:337`, `validation.py:38,539`.
- **EP-1** — Each re-does DB, project, settings, router, constitution, standards, topology and
  isolation, each omitting different parts. Where: 10 `RunContext` sites.
- **EP-3** — Isolation decided by three functions or skipped; only `sw implement` auto-escalates by
  DAL. Where: `implementation/interfaces/cli.py:331`, `flow/interfaces/cli.py:319`,
  `api/v1/pipelines.py:149`, `api/v1/_llm.py:146`.
- **EP-4** — Three router factories; API runs never set `config`; `sw run` loads settings twice.
  Where: `llm/interfaces/command.py:70,101`, `api/v1/_llm.py:27`, `flow/interfaces/cli.py:307,329`.
- **EP-5** — "Which project" answered differently per command; standards and profiles can come from
  the active project, not the target. Where: `implementation/interfaces/cli.py:274,306`,
  `review/interfaces/cli.py:344`, `flow/interfaces/cli.py:260,565`, `api/v1/validation.py:32`.
- **EP-12** — The API standards scan re-implements discovery, with a dot-folder bug. Where:
  `api/v1/standards.py:70`, `project/interfaces/cli.py:85,226`.
- **Real defect 5** — The API standards scan drops every file under a dot-folder in the absolute
  path; a project under `~/.local/...` scans zero files. Where:
  `interfaces/api/v1/standards.py:70-81`.
- **Real defect 10** — `sw resume` rebuilds the run for the current folder, not the run's own
  project. Where: `core/flow/interfaces/cli.py:565`.
- **CW-8** — "Project registered at this path" four times, two DB styles. Where:
  `workspace/store.py:87-115`, `_core.py:103`.
- **CW-9** — "Project name to root" five times with different checks; `discovery.py` has a different
  idea of "project root". Where: `settings_loader.py:117`, `_core.py:95`,
  `project/interfaces/cli.py:261`, `standards/interfaces/cli.py:36`, `api/v1/paths.py:33`.
- **CW-20** — The 5120-byte constitution limit is defined twice. Where:
  `constitution_loading.py:22`, `workspace/store.py:55`.
- **X-3** — Validation rules find the project root by different markers. Where:
  `c02_tests_exist.py:35`, `c03_tests_pass.py:98`, `c09_traceability.py:96`, `hasher.py:32`.
- **WV-19** — `sw draft` lives in review; each CLI hand-builds a one-step run using a private flow
  helper. Where: `review/interfaces/cli.py:148,181`, `implementation/interfaces/cli.py:256`,
  `cli_drift.py:203`.

## Goal

One run builder for every CLI command and API route: the same pipeline gets the same context through
every door.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-077`. Write each fix's test
red
first.
