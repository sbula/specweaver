# Walkthrough: TECH-076 SF-01 — One strict reader

- **Design**: [TECH-076_design.md](TECH-076_design.md)
- **Plan**: [TECH-076_sf01_implementation_plan.md](TECH-076_sf01_implementation_plan.md)

## CB-1 — FR-6 (one reader)

### What changed

- New `core/config/settings_file.py`: `SettingsFileError` (moved, same fields), `load_toml`,
  `validate` (unknown key first, no value in the message, `"Value error, "` removed — decision 2),
  `parse_section`.
- `llm_settings.py` lost its private `_load_toml` / `_validate`; `doc_policy.py` lost its own copy
  (key `(file)`, line 0 before Python 3.14) and passes its `[[docs.*]]` line finder to `validate`.
  `project_sections.py` is deleted; `autonomy_policy` and `implement_policy` import
  `parse_section` from `settings_file`.
- **Plan deviation:** every import of `SettingsFileError` (43 files in `src` and `tests`) now names
  `settings_file`. mypy refuses the implicit re-export from `llm_settings`, and a re-export would be
  a second home. SF-03's FR-8 keeps only the CLI handler's rename.

### Red first

- `test_settings_file.py`: collection error (no module); then, with the module in place and the
  callers not yet re-pointed, the agreement test failed: `[docs]` answered `(file)`.

### Combined analysis

Architecture: `settings_file.py` imports `tomllib`, `pydantic`, `toml_lines`; `core/config` stays
pure-logic. `tach check` clean. One reader replaces three.

| Function | Unit | Integration |
|---|---|---|
| `load_toml` | ✅ real line; line without `lineno` (forced) | — |
| `validate` | ✅ unknown key first; no value in the message; no prefix | — |
| `parse_section` | ✅ table, absent table, empty text | — |
| `parse_doc_policy` via the reader | ✅ agreement; `[[docs.rule]]` line (`test_doc_policy.py:65`) | ✅ existing loader tests |

Agreement: one broken text gives the same key, line and message from `[docs]`, `[llm]` and
`parse_section`. Mutants (all OBJECTED, pinned): `syntax-line-lost`, `unknown-key-not-first`,
`value-error-prefix-kept`, `docs-own-toml-reader`, `docs-array-line-lost`.

### Gates

Full suite 11372 passed, 9 skipped. `quality.py sf` 18/18 after the import re-point (mypy).

### Red/Blue (code)

- R1 (LOW) removing `"Value error, "` could change an `[llm]` message a user scripts against.
  Accepted: decision 2; the suite asserted none.
- R2 (LOW) `load_toml` now raises `from None` (was `from exc` in `llm_settings`): the traceback no
  longer chains the decode error. The message carries file and line; nothing read the chain.
- Cycle 2: no new finding.

## CB-2 — FR-1 and FR-2 (`[sandbox]` and `[standards]` strict)

### What changed

- `SandboxSettings` and `StandardsSettings` forbid unknown keys.
- `load_settings_async` reads `specweaver.toml` once and passes it through `parse_section` for both
  sections (`_project_sections`). The lenient `_load_toml_sandbox` / `_load_toml_standards` and
  their `except Exception` are gone: a `SettingsFileError` leaves `load_settings`.
- Guides: `subprocess_execution.md` (no host fallback), `pipeline_engine_guide.md` (`[sandbox]`),
  `3_managing_constitutions.md` (`[standards]`).

### Red first

`test_project_settings_strict.py`, written before the change: all 6 broken cases (broken TOML,
`execution_mod`, `"containr"`, a non-bool, `standards.mod`, `"copycat"`) loaded the defaults
(DID NOT RAISE). The 3 happy and boundary cases passed, as they must (NFR-2).

### Combined analysis

Architecture: `bootstrap/settings_loader` now imports `bootstrap/llm_settings_loader`
(`PROJECT_FILE_NAME`, `read_settings_text`) and `settings_file`, both inside `core/config`.
`tach check` clean. SF-03 FR-7 moves `PROJECT_FILE_NAME` out of the LLM loader.

| Function | Unit | Integration |
|---|---|---|
| `_project_sections` | ✅ no root → defaults | ✅ through `load_settings`: valid, no file, no section, 6 broken |
| `SandboxSettings` / `StandardsSettings` | ✅ existing model tests | ✅ unknown key cases |

Changed: `test_load_settings_toml_sandbox_malformed_falls_back_to_default` now expects the stop;
`test_session_policy_fullchain.py` used the removed `_load_toml_sandbox` and now calls
`_project_sections`. Gap story added: a project without a root path.

Mutants (all OBJECTED, pinned): FR-1 `sandbox-falls-back`, `standards-falls-back`; FR-2
`sandbox-accepts-unknown-key`, `standards-accepts-unknown-key`.

### Gates

Full suite 11382 passed, 9 skipped (first run: the full-chain test's import, fixed).
`quality.py sf` 18/18.

### Red/Blue (code)

- R1 (MEDIUM) `sw run` and the API still swallow the new error and run with isolation off. Known:
  SF-02 FR-4. Not pushed before SF-02.
- R2 (MEDIUM) `sw implement` / `sw review` on a broken `[sandbox]` now end in a traceback. Safer
  than the host fallback; SF-02 FR-5 turns it into the located message.
- R3 (LOW) `coder_sandbox` builds a container copy with `model_copy(update=…)`, which does not
  validate, so `extra="forbid"` does not touch it.
- Cycle 2: no new finding.

## CB-3 — FR-3 (`dal_definitions.yaml` strict)

### What changed

- `_load_dal_matrix` reads the file with ruamel's round-trip loader (line marks kept): invalid YAML
  → `SettingsFileError(…, "(syntax)", line, "not valid YAML")`; then `validate(DALImpactMatrix, …)`
  with a YAML line finder. Absent or empty file → the empty matrix, as before. The `except
  Exception` and its default are gone. The no-op `deep_merge_dict({}, data)` went with them.
- New `core/config/yaml_lines.py`: `yaml_line(data, path)`, the deepest key's line, else 1. It
  duck-types the marks, so `core/config` gains no ruamel import.
- `DALImpactMatrix`, `ValidationSettings`, `RuleOverride` forbid unknown keys.
- `special_patterns_and_adaptations.md` §6 said the file is "layered over the base presets"; the
  loader merged it into an empty dict. It now says what the code does: strict read here, the tier
  merged over the project's settings at validation time.

### Red first

The 5 broken DAL cases (YAML syntax, `matrx`, `overides`, a non-bool `enabled`, `DAL_Z`) loaded the
default matrix (DID NOT RAISE). The first syntax case was my guess at ruamel's line (3); ruamel
reports where it detects the error (4). I replaced it with a tab on line 3, which ruamel reports
on line 3, instead of copying the code's answer into the test.

### Combined analysis

| Function | Unit | Integration |
|---|---|---|
| `yaml_line` | ✅ nested, missing part, no marks, through a list | — |
| `_load_dal_matrix` | ✅ `test_dal_merge.py` (valid, missing, invalid YAML, wrong type) | ✅ valid, absent, empty, comment-only, 5 broken |

Changed: `test_load_settings_invalid_yaml` and `…_invalid_schema` expected the silent default; they
now expect the stop. Mutants (all OBJECTED, pinned): `dal-syntax-falls-back`, `dal-line-lost`,
`dal-matrix-accepts-unknown-key`, `dal-tier-accepts-unknown-key`.

### Gates

Full suite 11395 passed, 9 skipped. `quality.py sf` 18/18. `tach check` clean.

### Red/Blue (code)

- R1 (MEDIUM, **for the user**) `core/flow/handlers/validation.py:57-72`
  (`_resolve_merged_settings`) catches every error while layering the target's DAL tier over the
  settings and then validates with the tier **not applied**, logging a WARNING. That is a fourth
  fail-open spot, outside this ticket's findings. After this SF the file is validated on load, so
  the merge should not fail any more; the catch still hides it if it does.
- R2 (LOW) the YAML error message is fixed text; file content never reaches it.
- R3 (LOW) a matrix key ruamel loads as a non-string (`1:`) is refused by `DALLevel`, with the line
  of the deepest string key found.
- Cycle 2: no new finding.

## Decisions at the SF-01 stop (user, 2026-10-23)

CB-3 accepted. R1 (the validation handler's DAL merge catch-all) goes into SF-02 under FR-4.
