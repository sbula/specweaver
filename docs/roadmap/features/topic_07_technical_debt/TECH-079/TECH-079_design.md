# Design: Language and Toolchain Are Decided in a Dozen Places That Disagree

- **Feature ID**: TECH-079
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 10 below.

## Problem Statement

About 12 suffix tables and 5+ manifest readers decide a file's language and a project's build tool,
in conflicting order. A repo with `pyproject.toml` and `package.json` is TypeScript for generation
and Python for the container image.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **Fix first #6** — Two language detectors check manifests in opposite order; about 12
  suffix-to-language tables disagree (`.kts`, `.tsx`, `.js`). Where:
  `sandbox/language/core/_detect.py` vs `commons/prepare_plan.py:114`; tables in 12 files.
- **FL-4** — Suffix maps and manifest readers copied; they already differ. Where:
  `archetype_pipelines.py:28`, `contract_renderers.py:37`, `frameworks.py:30,98,110`,
  `task_files.py:185,202`.
- **AG-5** — Suffix and language tables disagree on `.kts`, `.tsx`, `.js`. Where: 12 tables.
- **SB-2** — Language and build-tool detection five-plus times, with conflicting order. Where:
  `_detect.py:47`, `prepare_plan.py:112`, `java/runner.py:113`, `kotlin/runner.py:65`,
  `frameworks.py:30`, `task_files.py:133`.
- **CW-10** — Toolchain and language decided by manifests with conflicting order. Where:
  `commons/prepare_plan.py:115`, `_detect.py:47`, `implement_policy.py:17`.
- **SB-7** — Three per-language if-ladders; only the runner one accepts a language override. Where:
  `qa_runner/core/factory.py:58`, `scenario_converter_factory.py:35`,
  `stack_trace_filter_factory.py:22`.
- **AG-6** — "Find a parser for this file" five times, some case-sensitive; parsers rebuilt per
  call. Where: `graph_adapter.py:62`, `code_structure/core/atom.py:107`, `tool.py:499`,
  `refactor/files.py:39`, `refactor/_base.py:34`, `orchestrator.py:158`.
- **AG-8** — Two "Analyzer" families with near-identical base names; 10, 5 and 3 languages
  supported. Where: `analyzers/factory.py:161` vs `standards/tree_sitter_base.py:31`.
- **WV-10** — "Archetype" means a layer role and a framework name in one field; planning keeps its
  own outdated archetype list. Where: `archetypes.md`, `archetype_pipelines.py:150`,
  `frameworks.py:51`, `planning/models.py:30`.
- **WV-11** — Framework languages declared twice; generation detects from `pom.xml`, validation only
  from the archetype. Where: `frameworks/*.md`, `evaluators/frameworks/*.yaml`,
  `pipelines/frameworks/java/`.

## Goal

One registry answers "which language, build tool and framework"; every caller asks it.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-079`. Write each fix's test
red
first.
