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
