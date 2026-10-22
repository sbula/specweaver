# Design: Project Settings Are Read Two Ways, and One Fails Open

- **Feature ID**: TECH-076
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 7 below.

## Problem Statement

`specweaver.toml` has a strict reader and a lenient one. `[sandbox]` and `[standards]` use the
lenient one, so a typo in `[sandbox]` silently falls back to host execution.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **Fix first #1** — `[sandbox]` and `[standards]` are read by a lenient copy of the TOML reader: a
  typo silently falls back to host execution; `[implement]`, `[autonomy]`, `[docs]`, `[llm]` stop
  with file and line. Where: `core/config/bootstrap/settings_loader.py:45-82` vs
  `core/config/project_sections.py:21`.
- **CW-1** — Strict and lenient `specweaver.toml` readers; `[sandbox]` falls back silently. Where:
  `project_sections.py:21` vs `bootstrap/settings_loader.py:45-80`.
- **CW-2** — Three copies of "TOML text to strict model to located error"; they report keys and line
  numbers differently. Where: `doc_policy.py:86,157`, `llm_settings.py:305,315`.
- **CW-3** — Each `specweaver.toml` section costs a model, a loader and a CLI wrapper;
  `PROJECT_FILE_NAME` lives in the LLM loader. Where: three `*_policy.py`, three `*_loader.py`,
  three wrappers in `interfaces/cli/_core.py:129`.
- **CW-4** — The shared settings error and its CLI handler are named as LLM things
  (`refuse_llm_settings` refuses doc and autonomy errors). Where: `llm_settings.py:49`,
  `_core.py:182`.
- **CW-18** — Schema, parsing, role resolution, currency and a CLI report in one module. Where:
  `llm_settings.py` (560 lines).
- **CW-19** — Text patching of marked blocks lives in config. Where: `doc_policy.py:130-154`.

## Goal

Every section goes through one strict reader that names the file and line of an error.

## Open Decisions (for the grilling, not answered here)

- `T-POSTURE`: a broken `[sandbox]` section stops the run, or warns and runs with isolation on.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-076`. Write each fix's test
red
first.
