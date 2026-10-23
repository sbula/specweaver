# Implementation Plan: Project Settings Are Read Two Ways, and One Fails Open [SF-01: One strict reader]
- **Feature ID**: TECH-076
- **Sub-Feature**: SF-01 — One strict reader
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-076/TECH-076_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-076/TECH-076_sf01_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-6 (one reader), FR-1 (`[sandbox]` / `[standards]` strict), FR-2 (unknown keys refused), FR-3
(`dal_definitions.yaml` strict). Kind `bugfix`. No dependency. NFR-1, NFR-2, NFR-3 apply.

## Research Notes

- **Three copies of the reader** (CW-2), read 2026-10-23:
  - `llm_settings._load_toml(text, source)` → `SettingsFileError(source, "(syntax)", line, "not valid TOML")`,
    line from the message (works before 3.14). `_validate(model, data, text, source, *, prefix)`:
    unknown key first, `[key]` parts dropped, message only (no `input`, it may be a secret).
  - `project_sections.parse_section(text, source, name, model)`: the same two steps for one table.
  - `doc_policy.parse_doc_policy(text, source)`: key `"(file)"`, line `getattr(exc, "lineno", 0)`
    (0 before 3.14), message with `"Value error, "` removed, its own `_line` for `[[docs.*]]`
    arrays (`path_line` cannot index arrays of tables).
- `SettingsFileError(source, key, line, message)` is defined in `llm_settings.py:49`, and
  `project_sections` / `doc_policy` import it from there. A shared reader in a new module that
  `llm_settings` itself calls would import back into `llm_settings`: a cycle. So the error moves
  into the new module now, and `llm_settings` imports it from there (its name stays importable from
  `llm_settings`; SF-03 FR-8 re-points the callers and renames the CLI handler).
- **Lenient readers** (`bootstrap/settings_loader.py`): `_load_toml_standards`, `_load_toml_sandbox`
  (open, `tomllib.load`, `Model(**data)`, `except Exception: logger.exception`), and
  `_load_dal_matrix` (ruamel `typ="safe"`, `DALImpactMatrix(**deep_merge_dict({}, data))`, same
  catch). All three feed `load_settings_async` (`settings_loader.py:121-145`).
- `read_settings_text(path) -> str` (`bootstrap/llm_settings_loader.py:62`) gives "" for a missing
  file: an absent file then parses to the model's defaults, as today (NFR-2).
- **Models**: `SandboxSettings`, `StandardsSettings`, `DALImpactMatrix`, `ValidationSettings`,
  `RuleOverride` (`core/config/settings.py:45-140`) are plain `BaseModel`s: unknown keys pass.
  None is built with extra keys in `src` (grep 2026-10-23); the suite confirms.
- **YAML lines**: ruamel's round-trip loader (`YAML(typ="rt")`) keeps marks: a `CommentedMap` has
  `.lc.key(k)` → `(line, col)` 0-based; a `YAMLError` has `problem_mark.line`. The DAL error key is
  the pydantic `loc` joined with dots (`matrix.DAL_E.overrides.S01.enabled`).
- **Tests asserting today's fallback** (change with this SF):
  `tests/unit/core/config/bootstrap/test_settings_loader.py:309`
  (`..._malformed_falls_back_to_default`), `tests/unit/core/config/test_dal_merge.py:125, 148`
  (`test_load_settings_invalid_yaml`, `..._invalid_schema`).
- Docs stating the fallback: `docs/dev_guides/subprocess_execution.md:193`.

## Decisions (Phase 4, user answered "all A" 2026-10-23)

1. `SettingsFileError` moves to `settings_file.py` in this SF; `llm_settings` imports it, and SF-03
   re-points the other imports.
2. The `"Value error, "` prefix is removed from every settings message.

## Approach (pseudocode, ordered)

**FR-6 — one reader** (new `core/config/settings_file.py`)
1. Move `SettingsFileError` here unchanged (AD-2). `llm_settings` imports it.
2. `load_toml(text, source) -> dict`: today's `_load_toml` (key `"(syntax)"`, line from the
   message, else 1).
3. `validate(model, data, text, source, *, prefix, line_of=path_line)`: today's `_validate`; the
   line finder is a parameter so `[docs]` passes its array-aware `_line` and YAML passes its own.
   Strip `"Value error, "` from the message for every caller (today only `[docs]` does).
4. `parse_section(text, source, name, model)` = `validate(model, load_toml(...).get(name, {}), ..., prefix=(name,))`.
5. Re-point `llm_settings.parse_machine_file` / `parse_project_llm`, `doc_policy.parse_doc_policy`
   and `project_sections` (kept as a thin import or folded in) to these. `[docs]` keeps its
   `_one_block_each` check after validation.

**FR-1, FR-2 — `[sandbox]` / `[standards]`**
6. `SandboxSettings`, `StandardsSettings`: `extra="forbid"` (same config as `_Strict`).
7. `load_settings_async`: read the text once (`read_settings_text(root / "specweaver.toml")`), then
   `parse_section(text, source, "sandbox", SandboxSettings)` and the same for `standards`. No catch:
   `SettingsFileError` leaves `load_settings`. Delete `_load_toml_sandbox`, `_load_toml_standards`.

**FR-3 — `dal_definitions.yaml`**
8. `DALImpactMatrix`, `ValidationSettings`, `RuleOverride`: `extra="forbid"`.
9. `_load_dal_matrix`: absent file → default (unchanged); read the text; `YAML(typ="rt")`;
   `YAMLError` → `SettingsFileError(source, "(syntax)", mark.line + 1, "not valid YAML")`; empty → `{}`;
   then `validate(DALImpactMatrix, data, ..., line_of=<yaml line of loc>)`. The line finder walks
   the loaded map by `loc` and answers the deepest key's line + 1, else 1. No catch.

> [!WARNING]
> Between this SF and SF-02, `sw implement` / `sw review` on a broken `[sandbox]` end in a
> traceback instead of running on the host; `sw run` and the API still swallow it (SF-02 fixes
> both). The feature is pushed once, after SF-02 and SF-03, so the interim never ships.

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/core/config/settings_file.py` [NEW] | `SettingsFileError`, `load_toml`, `validate`, `parse_section` |
| `src/specweaver/core/config/llm_settings.py` [MODIFY] | uses the shared reader; imports the error |
| `src/specweaver/core/config/doc_policy.py` [MODIFY] | uses the shared reader; keeps `_line` and `_one_block_each` |
| `src/specweaver/core/config/project_sections.py` [MODIFY or DELETE] | folded into `settings_file.py`; callers re-pointed |
| `src/specweaver/core/config/settings.py` [MODIFY] | `extra="forbid"` on the five models |
| `src/specweaver/core/config/bootstrap/settings_loader.py` [MODIFY] | strict sections and DAL file; lenient functions removed |
| `src/specweaver/core/config/yaml_lines.py` [NEW] | the line of a `loc` in a ruamel round-trip map |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-6 | unit | `tests/unit/core/config/test_settings_file.py` [NEW] | valid table (happy); absent table → defaults; empty text (boundary); syntax error → key `(syntax)` and its real line, also when `lineno` is missing (Python < 3.14, forced) (degradation); unknown key reported before a missing one; message carries no value (hostile, a secret-looking value) |
| FR-6 | unit | same | **agreement**: one broken text gives the same key and line from `[docs]`, `[llm]` and `parse_section`. Red today: `[docs]` says `(file)` |
| FR-1, FR-2 | integration | `tests/integration/core/config/test_project_settings_strict.py` [NEW] | `load_settings` through a real DB row: valid `[sandbox]` / `[standards]` (happy); absent file, absent section (boundary, NFR-2); broken TOML; `execution_mod` (unknown key); `"containr"` (bad value); `[standards] mod = …` → `SettingsFileError` naming `specweaver.toml`, the key and its line (hostile). Red today: all give `host` / `mimicry` |
| FR-3 | integration | same file | DAL: valid overlay (happy); absent, empty (boundary); broken YAML → its line; unknown key, `enabled: "not_a_boolean"` → key path and line (hostile). Red today: default matrix |
| — | unit (changed) | `test_settings_loader.py:309`, `test_dal_merge.py:125,148` | now expect `SettingsFileError` |

Mutants to write to `TECH-076_mutants.json`:
- FR-1: `load_settings_async` catches `SettingsFileError` and uses `SandboxSettings()`.
- FR-2: `SandboxSettings` without `extra="forbid"`.
- FR-3: `_load_dal_matrix` returns the default on a `SettingsFileError`.
- FR-6: `load_toml` reports line 1 always; `validate` sorts without "unknown key first".

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | FR-6: `settings_file.py`, the three callers re-pointed. Agreement test written first, red | unit green; FR-6 mutants killed; existing settings tests green |
| CB-2 | FR-1, FR-2: strict `[sandbox]` / `[standards]`. Integration test written first, red | integration green; FR-1, FR-2 mutants killed |
| CB-3 | FR-3: strict DAL file. Closes SF-01: stops for the user's acceptance | integration green; FR-3 mutant killed |

## Documentation

`subprocess_execution.md:193` and `pipeline_engine_guide.md` (`[sandbox]`): a broken section stops,
naming file and line. `special_patterns_and_adaptations.md:93` (DAL file): the same.

## Audit (Phase 2) — answered: all A, 2026-10-23

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | `SettingsFileError` must move to the new module in SF-01, not SF-03, or the shared reader and `llm_settings` import each other. | A: move it now; `llm_settings` imports it, so old imports still work until SF-03 re-points them. B: keep the reader inside `llm_settings` until SF-03. | A — no cycle, one move | LOW |
| 2 | `[docs]` today removes pydantic's `"Value error, "` prefix; `[llm]` and the other sections do not. One reader means one choice. | A: remove it everywhere (the message reads as the rule's own words). B: keep it everywhere. | A | LOW |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| `settings_file.py`, `yaml_lines.py` | `core/config` | none (text in, model out) | none | none | `tomllib`, `pydantic`, `ruamel` (already used) | settings files | ok |
| `settings_loader.py` | `core/config/bootstrap` | reads two files (as today) | none | none | none new | project settings | ok |

No new module edge, no cycle (the error moving out of `llm_settings` removes one), no `tach.toml`
change. No CRITICAL architecture finding.

## Consistency Check and Red/Blue (Phase 5)

- **Coverage**: FR-6 (CB-1), FR-1 and FR-2 (CB-2), FR-3 (CB-3). NFR-1: no catch is left around a
  settings read in `load_settings`. NFR-2: absent file, absent section and empty DAL file give the
  defaults (tested). NFR-3: the message keeps `source:line: key: message`. AD-1 (one reader),
  AD-2 (same error fields) hold. FR-4 and FR-5 (the doors) are SF-02's.
- **Open questions**: none. All decisions are resolved and documented inline in the plan.
- **Handoff risk**: a fresh agent might keep the old `except Exception` "to be safe": the three
  catches in `settings_loader.py` must go. The three old tests asserting the fallback must change,
  not be skipped.
- **Architecture**: `settings_file.py` imports only the standard library and `pydantic`;
  `llm_settings`, `doc_policy`, `settings_loader` import it. The cycle risk is removed by the move.
- **DDD/KISS/DRY/hexagonal/SoC**: one reader replaces three; the line finders stay per format
  (TOML tables, `[[docs.*]]` arrays, YAML maps) because each format locates keys differently.
- **Code detail limit**: no code block; steps are pseudocode.
- **Red/Blue**, 2 cycles:
  - R1 (MEDIUM) removing `"Value error, "` changes `[llm]` messages some tests may assert. Blue:
    decision 2; the full suite shows each one, and the fix is the expected text.
  - R2 (MEDIUM) a project with no root path. Blue: no file is read; defaults, as today.
  - R3 (MEDIUM) DAL keys are `DALLevel` names; pydantic's `loc` gives the same text as the YAML
    key, so the line finder matches. Covered by the hostile case.
  - R4 (LOW) a YAML error message could echo file content. Blue: the message is fixed text
    (`not valid YAML`), only the line comes from the mark.
  - Cycle 2: no new finding. Below every threshold.
