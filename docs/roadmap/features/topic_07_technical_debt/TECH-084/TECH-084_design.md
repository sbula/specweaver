# Design: A File's Pipeline Is Chosen Three Ways

- **Feature ID**: TECH-084
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 7 below.

## Problem Statement

The validation pipeline for a file is chosen three ways and pipeline YAML is loaded five ways, so
`sw check`, `sw run` and the API judge the same file by different rules.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **Fix first #9** — A file's validation pipeline is chosen three ways (the API never applies the
  archetype); pipeline YAML is loaded five ways (`sw run` ignores project overrides); "shipped file,
  project file first" exists four times with different rules. Where:
  `assurance/validation/pipeline_loader.py`, `core/flow/handlers/archetype_pipelines.py`,
  `core/flow/engine/parser.py`.
- **WV-1** — Validation pipeline chosen three ways; the API never applies the archetype; a missing
  profile errors in CLI but falls back in flow. Where: `pipeline_loader.py:125`,
  `archetype_pipelines.py:48`, `validation/interfaces/cli.py:98,270`, `api/v1/validation.py:85`.
- **WV-2** — Pipeline YAML loaded five ways; only validation honours project overrides; two kinds of
  YAML share one folder. Where: `pipeline_loader.py:69`, `parser.py:72,104`, `decompose.py:210`,
  `dual_pipeline.py:123`, `profiles.py:68`.
- **WV-3** — Four override loaders: replace vs deep-merge; the front-matter regex copied. Where:
  `rubrics/loader.py:46`, `implementation/languages.py:85`, `evaluators/loader.py:155`,
  `pipeline_loader.py:75`.
- **FL-14** — Sub-pipelines built from raw YAML with PyYAML, skipping `validate_flow`. Where:
  `decompose.py:210`, `dual_pipeline.py:121` vs `parser.py:30`.
- **CW-12** — Profiles reach into `workflows/pipelines` by file path; override order differs from
  the pipeline loader and from itself; depends on the working folder. Where:
  `core/config/profiles.py:66-75,122,179`.
- **WV-20** — Old rule runner used only by tests. Where: `validation/runner.py` vs
  `executor.py:342`.

## Goal

One selector and one loader; every door honours project overrides the same way.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-084`. Write each fix's test
red
first.
