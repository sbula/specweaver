# Design: Spec Names and Sections Are Parsed Several Ways

- **Feature ID**: TECH-083
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 5 below.

## Problem Statement

Spec file names, sections and artifact paths are derived several ways. S07 accepts only `## 2.
Contract`, while generation accepts any number, so `## 3. Contract` passes generation and fails
validation.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **FL-2** — Spec naming (feature suffix, feature name, artifact paths) spelled several ways; one
  file mixes `stem` and `module_stem`. Where: `draft.py:26`, `decomposition_artifacts.py:32`,
  `feature_drafter.py:169`, `reviewed_spec.py:38,100`.
- **FL-13** — Two draft handlers copied; resume hints already differ (`sw run --resume` vs `sw
  resume`). Where: `draft.py:49-119` vs `214-298`.
- **FL-15** — "Write a tagged YAML next to the spec" and "spec lineage parent" copied. Where:
  `generation.py:267,364,438`, `decomposition_artifacts.py:97`, `draft.py:90,269`.
- **WV-9** — Spec section extraction copied; S07 accepts only "2.". Where:
  `contract_renderers.py:365`, `s07_test_first.py:224,243`, `scenario_generator.py:178`.
- **Real defect 1** — S07 accepts only `## 2. Contract` or `## Contract`; the generator accepts any
  number, so `## 3. Contract` passes generation and fails validation. Where:
  `rules/spec/s07_test_first.py:228` vs `handlers/contract_renderers.py:368`.

## Goal

One spec model names spec files and reads sections for every caller.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-083`. Write each fix's test
red
first.
