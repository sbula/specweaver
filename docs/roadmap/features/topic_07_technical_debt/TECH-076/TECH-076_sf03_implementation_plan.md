# Implementation Plan: Project Settings Are Read Two Ways, and One Fails Open [SF-03: One loader, honest names, one home each]
- **Feature ID**: TECH-076
- **Sub-Feature**: SF-03 — One loader, honest names, one home each
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-076/TECH-076_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-076/TECH-076_sf03_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-7 (one loader, one CLI wrapper, `PROJECT_FILE_NAME` home, `load_settings_for_active` removed),
FR-8 (settings names, not LLM names), FR-9 (`llm_settings.py` split), FR-10 (doc block helpers to
`commons`). Kind `bugfix` (structural part of the ticket). No behaviour change: NFR-2 and NFR-3 —
every existing test stays green with only its imports changed. Depends on SF-01 (committed).

## Research Notes

- **Three section loaders** (`core/config/bootstrap/{autonomy,implement,doc_policy}_loader.py`), each
  `path = root / PROJECT_FILE_NAME; return parse_x(read_settings_text(path), str(path))`.
  `PROJECT_FILE_NAME` and `read_settings_text` live in `bootstrap/llm_settings_loader.py`, which
  also reads the machine file and `keys.env`. Users of the three loaders and their CLI wrappers:
  18 call sites in 9 files (`interfaces/cli/_core.py`, `interfaces/api/v1/run_settings.py`,
  `core/flow/interfaces/cli.py`, tests).
- **CLI wrappers** (`interfaces/cli/_core.py`): `load_doc_policy_at`, `load_autonomy_at`,
  `language_at` — the same try/refuse shape three times, plus `load_project_settings` (SF-02).
- **Handler name** (CW-4): `refuse_llm_settings` — 14 references in `src` and `tests`; it refuses
  every settings error. `SettingsFileError` already lives in `core/config/settings_file.py` (SF-01).
- **Dead code**: `load_settings_for_active` (`bootstrap/settings_loader.py:147`) has no caller.
- **`llm_settings.py`** (522 lines): models and money helpers (`ServerEntry` … `ProjectLlmSection`,
  `format_money`, `to_usd`, `brake_limits`); parsing (`parse_machine_file`, `parse_project_llm`,
  schema-version check, machine-only key check); file layering (`LlmSettingsFiles`); role resolution
  and the CLI report (`ResolvedRole`, `resolve_roles`, `settings_report`, row helpers). 79 files
  import from it.
- **Doc blocks** (`core/config/doc_policy.py:121-160`): `_markers`, `_span`, `fill_block`,
  `outside_blocks`; users `core/flow/handlers/bash_action.py:93`, `sandbox/git/core/worktree_ops.py:13`,
  `tests/unit/core/config/test_doc_blocks.py`. `commons` is not a `tach` module (no rules), and its
  `context.yaml` `exposes` list names what it offers.

## Decisions (Phase 4, user answered "all A" 2026-10-23)

1. One generic `load_section(root, parse)`; the three loader modules are deleted.
2. `LlmSettingsFiles` goes with the parsing (`llm_settings_parse.py`).

## Approach (pseudocode, ordered)

**Task 0 — drifted mutants (found in Phase 5)**
0. Ten mutants in other corpora no longer find their anchor: eight because TECH-075 SF-02 and
   TECH-076 SF-01/SF-02 moved code (`pipelines.py` ×7: D-INTL-08, C-EXEC-08 ×2, C-FLOW-11,
   B-FLOW-07 ×2, D-UI-01; `llm_settings.py`: C-FLOW-13 `missing-reported-before-typo`), two in
   `workspace/analyzers/chunking.py` (B-SENS-03) from earlier work. Re-point each to where its
   behaviour now lives, run it with `_mutate.py` (must be OBJECTED), re-pin with `_corpus.py`. The
   nightly run reports drift on its own; this only stops the morning gate from inheriting it.
   SF-03's own moves re-point their mutants in the boundary that moves the code.

**FR-7, FR-8 — one loader, one wrapper, honest names**
1. New `bootstrap/project_settings.py`: `PROJECT_FILE_NAME`, `read_settings_text` (moved from the LLM
   loader, which imports them), and `load_section(project_root, parse) -> T` where
   `parse(text, source)` is the section's parser.
2. Delete the three `*_loader.py`; callers use `load_section(root, parse_autonomy)` etc.
3. `_core.load_section_at(path, parse) -> T`: `load_section`, refusing a `SettingsFileError`.
   It replaces `load_doc_policy_at`, `load_autonomy_at` and `language_at` (`.language` at the call).
4. Rename `refuse_llm_settings` → `refuse_settings` everywhere.
5. Delete `load_settings_for_active`.

**FR-10 — doc blocks**
6. Move `_markers`, `_span`, `fill_block`, `outside_blocks` to `commons/doc_blocks.py`; add the two
   public names to `commons/context.yaml` `exposes`; re-point the two users and the test.

**FR-9 — split `llm_settings.py`**
7. `llm_settings.py` keeps the models and the money helpers (the schema).
8. `llm_settings_parse.py`: parsing and `LlmSettingsFiles` (text → models → layered files).
9. `llm_roles.py`: `ResolvedRole`, `resolve_roles`, `_refuse_hosted`, the report and its row helpers.
10. Re-point the importers by name (scripted), then `ruff` isort.

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/core/config/bootstrap/project_settings.py` [NEW] | file name, text reader, `load_section` |
| `src/specweaver/core/config/bootstrap/{autonomy,implement,doc_policy}_loader.py` [DELETE] | replaced by `load_section` |
| `src/specweaver/core/config/bootstrap/llm_settings_loader.py` [MODIFY] | imports the moved names |
| `src/specweaver/core/config/bootstrap/settings_loader.py` [MODIFY] | `load_settings_for_active` removed |
| `src/specweaver/interfaces/cli/_core.py` [MODIFY] | `load_section_at`; `refuse_settings` |
| `src/specweaver/commons/doc_blocks.py` [NEW] | block helpers |
| `src/specweaver/core/config/llm_settings_parse.py`, `llm_roles.py` [NEW] | the split |
| callers in `src` and `tests` [MODIFY] | imports and names only |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-7 | unit | `tests/unit/core/config/bootstrap/test_project_settings.py` [NEW] | `load_section` reads `[autonomy]`, `[implement]`, `[docs]` (happy); no file → each parser's empty value (boundary); a broken file → the same `SettingsFileError` for all three (agreement, degradation); BOM-prefixed file still read (hostile encoding). Red first: no module |
| FR-7 | unit | `tests/unit/interfaces/cli/test_project_path_or_exit.py` (extended) | `load_section_at` returns the section; a broken file exits 1 with the located message |
| FR-8 | — | **[proof: arch — the suite and `ruff`]** | the rename leaves no `refuse_llm_settings`; a grep test is not added (names are not behaviour) |
| FR-9 | — | **[proof: arch — file size and import gates]** | every existing `llm_settings` test passes against the new homes; `llm_settings.py` falls below the size warning |
| FR-10 | unit | `tests/unit/core/config/test_doc_blocks.py` → moved to `tests/unit/commons/test_doc_blocks.py` | unchanged cases, new import. Red first: import from `commons` fails before the move |

Mutants to write to `TECH-076_mutants.json`: FR-7 `load_section` reads a fixed empty text;
`load_section_at` re-raises. (FR-8, FR-9, FR-10 change no behaviour; their existing mutants are
re-pointed where the code moved.)

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | Task 0 (drifted mutants), FR-7, FR-8: loader, wrapper, rename, dead code | suite green; every corpus anchor found; FR-7 mutants killed |
| CB-2 | FR-10: doc blocks to `commons` | suite green; existing block mutants (if any) re-pointed |
| CB-3 | FR-9: the `llm_settings` split. Closes SF-03 and the last SF: stops for the user's acceptance | suite green; `sf` gate green; moved mutants re-pinned |

## Documentation

`docs/dev_guides` pages naming `refuse_llm_settings`, the `*_loader` modules, `llm_settings`
functions or `doc_policy.fill_block` (grep at each boundary); `commons/context.yaml` `exposes`.

## Audit (Phase 2) — answered: all A, 2026-10-23

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | CW-3: how far "one loader" goes. | A: one generic `load_section(root, parse)`; the three loader modules are deleted. B: keep thin per-section functions over a shared helper. | A — adding a section then costs a model and a parser only | LOW |
| 2 | FR-9: where `LlmSettingsFiles` (layering the machine file over the project section) goes. | A: with parsing (`llm_settings_parse.py`): text → models → layered files is one path. B: with role resolution (`llm_roles.py`). | A — role resolution reads the layered files; it does not build them | LOW |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| `project_settings.py` | `core/config/bootstrap` · adapter | reads `specweaver.toml` (as the loaders did) | none | none | none new | settings files | ok; keeps `test_settings_files_have_one_reader.py` true (only bootstrap opens settings files) |
| `doc_blocks.py` | `commons` · pure | none | none | none | none | text | ok |
| `llm_settings_parse.py`, `llm_roles.py` | `core/config` · pure-logic | none | none | none | within `core/config` | LLM settings | ok |

No new module edge, no cycle (`llm_roles` → `llm_settings_parse` → `llm_settings`), no `tach.toml`
change. No CRITICAL architecture finding.

## Consistency Check and Red/Blue (Phase 5)

- **Coverage**: FR-7, FR-8 (CB-1), FR-10 (CB-2), FR-9 (CB-3). NFR-2/NFR-3: imports and names change,
  behaviour does not; the suite is the proof. AD-2 (same error type) holds.
- **Open questions**: none. All decisions are resolved and documented inline in the plan.
- **Handoff risk**: a move breaks mutants in *other* features' corpora (anchors by file and text).
  After every move, run the anchor check (every corpus `old` text found in its `file`) before the
  commit; the commit gate does not run it.
- **Architecture**: no new edge; `test_settings_files_have_one_reader.py` stays true (the new loader
  is in `bootstrap`).
- **DDD/KISS/DRY/hexagonal/SoC**: one loader, one wrapper; each LLM settings module has one reason
  to change; text patching leaves config.
- **Code detail limit**: no code block; steps are pseudocode.
- **Red/Blue**, 2 cycles:
  - R1 (HIGH) moving code silently breaks other corpora's anchors (found: 10 already drifted).
    Blue: valid. Task 0 fixes them; the anchor check runs at every boundary of SF-03.
  - R2 (MEDIUM) 79 files import from `llm_settings`. Blue: re-pointed by a script keyed on the moved
    names, then `ruff` isort, `mypy` and the full suite.
  - R3 (LOW) docs naming old functions. Blue: grep at each boundary (Documentation section).
  - Cycle 2: no new finding. Below every threshold.
