# Walkthrough: TECH-076 SF-03 — One loader, honest names, one home each

- **Design**: [TECH-076_design.md](TECH-076_design.md)
- **Plan**: [TECH-076_sf03_implementation_plan.md](TECH-076_sf03_implementation_plan.md)

## CB-1 — Task 0 (drifted mutants), FR-7 (one loader, one wrapper), FR-8 (names)

### Task 0 — drifted mutants

A mutant finds its code by file and exact text, and nothing at commit time checks that it still
does (the nightly run reports drift the morning after). Before this boundary 10 mutants in other
corpora no longer found their code: 8 because TECH-075 SF-02 and TECH-076 SF-01/SF-02 moved it
(`_project_policy` → `run_settings.project_policy`, `_max_runs` → `run_settings.max_runs`,
`llm_settings._validate` → `settings_file.validate`), 2 in B-SENS-03 from earlier work (`_split`
moved to `_sizing.emit_split`; the dot filter became `chunk_source`'s containment-based `tops`).
This boundary's own moves drifted 7 more (the `sw run` / `sw implement` reads of `[docs]`,
`[autonomy]`, `[implement]`; `read_settings_text`; TECH-076's own FR-5 mutant after the rename).
All 17 point at today's code, each was run (OBJECTED) and re-pinned. The anchor check runs before
every SF-03 commit (`.tmp/anchors.py`: every corpus `old` text found in its `file`).

**A trap found on the way:** `scripts/_mutate.py --tests` takes one value and the last one wins;
several paths go in one space-separated value. Passing `--tests a --tests b --tests c` ran only `c`
and reported three mutants SILENT that the full scope kills.

### What changed

- New `core/config/bootstrap/project_settings.py`: `PROJECT_FILE_NAME`, `read_settings_text`
  (moved from the LLM loader), `load_section(project_root, parse)`. The three `*_loader.py` modules
  are deleted (decision 1); `tach.toml`'s bootstrap interface lists `project_settings.load_section`.
- `interfaces/cli/_core.py`: `load_section_at(path, parse)` (one refusal) and
  `project_sections_at(path)` (`[docs]`, `[autonomy]`, `[implement]` language, read together by
  both run roots) replace `load_doc_policy_at`, `load_autonomy_at`, `language_at`.
- `refuse_llm_settings` → `refuse_settings` in `src` and `tests` (FR-8). The closed C-FLOW-13 plan
  keeps the old name as history.
- `load_settings_for_active` removed with its two tests and its `context.yaml` entry.

### Red first

- `test_project_settings.py`: collection error (no module).
- **Process slip:** `load_section_at` / `project_sections_at` were written before their two tests
  in `test_project_path_or_exit.py`, which passed on first run. Proof instead: mutants
  `cli-section-error-escapes` (OBJECTED) and `loader-reads-nothing` (OBJECTED, 7 tests).

### Combined analysis

| Function | Unit | Integration |
|---|---|---|
| `load_section` | ✅ three sections, no file, BOM, broken file alike for all | ✅ doc policy and autonomy loader tests |
| `load_section_at`, `project_sections_at` | ✅ read together; broken section exits naming its line | ✅ run e2e and API tests |

Agreement: one broken file gives the same error for `[autonomy]`, `[implement]` and `[docs]`.

### Gates

Full suite 11438 passed, 9 skipped. `quality.py sf` 18/18. `tach check` clean (after the interface
list update). Drifted mutants: 0.

### Red/Blue (code)

- R1 (HIGH) moving code drifts other corpora silently. Fixed for this boundary (17 re-pointed);
  the anchor check runs before each remaining SF-03 commit. Not added as a commit gate: that is a
  tooling change outside this ticket, and the nightly run already reports drift.
- R2 (LOW) `project_sections_at` reads the file three times. Accepted: three small reads at a run's
  start; one parse per section keeps each parser's own error.
- Cycle 2: no new finding.
