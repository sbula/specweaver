# Walkthrough: TECH-075 SF-01 — The boundary refuses every way out

- **Design**: [TECH-075_design.md](TECH-075_design.md)
- **Plan**: [TECH-075_sf01_implementation_plan.md](TECH-075_sf01_implementation_plan.md)

## CB-1 — FR-1: `WorkspaceBoundary` refuses every way out

### What changed

- `sandbox/security.py`:
  - `validate_path` joins a relative path to the primary root before it resolves. Before, it
    resolved against the process folder.
  - A null byte is a `WorkspaceBoundaryError`. Before, it was a `ValueError`.
  - A relative path on a boundary with no root (`ReadOnlyWorkspaceBoundary`) is refused. Before, it
    was an `IndexError`.
  - `resolve_relative` refuses an empty or whitespace-only path. Before, it meant the root.
- `anti_patterns.md`: the row that called `WorkspaceBoundary` a parallel guard now says it is the
  one guard for paths from outside (AD-1). `FileExecutor._validate_path` stays (AD-5).

### Red first

7 new tests failed before the code: empty (3 cases), null byte (2), relative judged by the
process folder (1), read-only boundary (1). The reason each time was the old behaviour (no error,
`ValueError`, a path under the process folder, `IndexError`).

### Combined analysis (pre-commit Phases 1–2)

Architecture: one file changed in `sandbox`; no new import, module or edge. No finding.

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `WorkspaceBoundary.validate_path` | ✅ | ✅ (script atom, unchanged caller) | — |
| `WorkspaceBoundary.resolve_relative` | ✅ | — (no caller yet; SF-02 adds them) | — |

Gap found and closed (Phase 3): no test proved links are resolved before the check (NFR-3).
Added: a link pointing outside is refused; a link pointing inside is allowed. Both fail when
`resolve()` is replaced by `abspath`.

Composition: `resolve_relative` always calls `validate_path`; the tests drive it through
`resolve_relative`. Agreement: `FileExecutor._validate_path` does a similar job but refuses every
link, by design (AD-5), so no agreement test.

### Results

- `tests.py cb TECH-075 --kind bugfix`: unit ok, integration ok.
- `tests/unit/sandbox` + `tests/integration/sandbox`: 2036 passed, 9 skipped.
- `quality.py cb`: 17 of 17 passed. `quality.py doc`: 14 of 14 passed.
- Mutants (`TECH-075_mutants.json`, FR-1): `null-byte-passes`, `empty-path-is-root`,
  `relative-judged-by-cwd` — all killed, hashes pinned.

### Decisions

No stop. Roadmap: `TECH-075` moved to 🟡 (in progress).

## CB-2 — FR-4: the protocol atom and tool read only inside the boundary

### What changed

- `ProtocolAtom(boundary)` — the boundary is required (NFR-1). `run()` checks the path before it
  opens the file. A refusal is `FAILED` with "Path is outside the workspace: <as given>"; a missing
  file is named as given, not as resolved.
- `ProtocolTool(boundary)`; the registry builds it with the run's boundary (`kwargs["boundary"]`).
  With no boundary the registry builds no protocol tool.
- `discover_protocol_endpoints` (C13's contract scan) builds the atom over the project root. It
  also checks the boundary **before** it sniffs a file's head: a link to an outside contract was
  read by that sniff, even though the atom then refused it. Only contract suffixes are checked, so
  a link out to a `.py` file logs nothing.
- `WorkspaceBoundary.contains(path) -> bool`: `core.flow` may not import `WorkspaceBoundaryError`
  (not in `sandbox`'s tach interface), and NFR-5 keeps `tach.toml` unchanged. So the hydrator asks
  `contains`.

### Red first

20 atom tests red before the change (no boundary parameter; `ProtocolAtom()` still built). Tool and
registry tests red with `TypeError`. The seam test for the scan went red for the right reason once
the atom had a boundary: the head sniff opened `outside/api.yaml`. `contains` test red
(`AttributeError`).

### Combined analysis

Architecture: `sandbox.protocol` imports `sandbox.security` (same tach module); `core.flow` already
consumes `sandbox/security` and uses only `WorkspaceBoundary`. `tach` clean. No new edge.

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `ProtocolAtom.run` | ✅ | ✅ (through the dispatcher) | — |
| `ProtocolTool.extract_schema_*` | ✅ both intents | ✅ | — |
| `create_protocol` (registry) | ✅ | ✅ run's boundary; none → no tool | — |
| `discover_protocol_endpoints` | — | ✅ inside, link in, link out, never opened, quiet non-contract | ✅ (C13 pipelines, unchanged) |
| `WorkspaceBoundary.contains` | ✅ | ✅ (via the scan) | — |

Found and fixed during the gate: `lost_errors` wanted an `# expected:` reason on the atom's
`except`; `tach` refused the error import (→ `contains`). An old conformance test built the protocol
tool with no boundary; it now passes one, and a new test proves no boundary means no tool.

### Results

- `tests.py cb TECH-075 --kind bugfix`: unit ok (6 paths), integration ok (2 paths).
- `quality.py cb`: 17 of 17. `quality.py doc`: 14 of 14.
- Mutants (FR-4): `read-before-check`, `tool-without-run-boundary`, `sniff-before-check` — killed,
  hashes pinned.

### Decisions

No stop. `contains` is a new public method on an exposed class, chosen to keep `tach.toml`
unchanged (NFR-5); review it.

## CB-3 — FR-5: every QA intent refuses a path outside its root

### What changed

- `QARunnerAtom.run` checks every path argument before any intent runs: `target`, each `targets`
  entry, and the debugger's `entrypoint` (agreed 2026-10-22). Each must pass
  `WorkspaceBoundary([cwd]).contains`, or be `/scenarios/…` in a scenario run. A blank or non-string
  value is refused. An empty value is skipped, so each intent still names what is missing.
- `_traversal_error` (only `run_tests` called it) is removed. The scenario-mount tests now go
  through `run()` instead of the private helper.
- A Java or Kotlin main-class name (`com.example.Main`) passes: it resolves inside the root as a name.

### Red first

26 of the new unit cases failed before the code: five intents had no check, and `run_tests` let a
null byte through as "Invalid target path". The seam test was written after the code, so it was run
against the old atom (`git show HEAD:…`, then restored): 16 of 20 failed; the 4 that passed are
`run_tests`, which had a check, and the inside case.

### Combined analysis

Architecture: `sandbox.qa_runner.core` imports `sandbox.security` (same tach module). No new edge.

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `QARunnerAtom.run` → `_refused_path` | ✅ six intents × outside, link, null byte; targets; entrypoint; types; blank | ✅ through `create_qa_runner_interface`, real runner, no process starts | — |
| `_given_paths`, `_stays_inside` | ✅ via `run` | ✅ | — |
| `_in_scenarios_mount` | ✅ mounted / not mounted | — | ✅ scenario pipelines (unchanged) |

Gaps found in the gate and closed: `targets` given as one string; a whitespace-only target.
Engine callers (`validation.py`, `lint_fix.py`, `validation_hydrator.py`, scenario steps) pass
relative targets inside `cwd`; their tests stay green.

Found in the gate, and what was done:

- `complexipy`: `_refused_path` reached 16. Split into `_given_paths` and `_stays_inside`.
- `ruff` SIM105 in the seam test. Fixed.
- `duplication`: the intent dispatch copied in `FileSystemAtom.run` and `QARunnerAtom.run` is an
  old clone; the edit re-keyed it and it shrank from 23 to 14 lines. Re-frozen
  (`scripts/baselines/duplication.json`). No audit ticket owns it; the baseline keeps it from
  growing.
- `nfr_sweep`: `B-EXEC-01` NFR-3 (`--network none`) and NFR-4 (non-root, `--cap-drop ALL`,
  `no-new-privileges`) were "cited" only because `test_qa_runner_atom.py` names `B-EXEC-01` once and
  has old "NFR-3/NFR-4 Edge Case" docstrings that mean something else. The new `Proves: TECH-075`
  line took those words, so the false citation fell away. The real proof was read and cited:
  `test_container_executor.py` (`test_network_none_present`, `test_capabilities_dropped`,
  `test_user_flag_matches_invoking_uid_on_linux`) and the real-engine
  `test_network_none_blocks_egress`.
- The first `tests.py sf` run reported a unit failure that did not come back in a rerun or in three
  runs of the test it printed. Not reproduced; the commit gate runs the full suite again.

### Results

- `tests.py sf TECH-075 --kind bugfix`: unit 9170 passed, 9 skipped; integration 1686 passed;
  e2e (domain) 34 passed.
- `quality.py sf`: 18 of 18. `quality.py doc`: 14 of 14.
- Mutants (FR-5): `linter-unchecked`, `entrypoint-unchecked`, `scenarios-without-mount` — killed,
  hashes pinned. A blank-target mutant was killed too (not in the corpus).

### Decisions

SF-01 closes here: stopped for the user's acceptance before the commit.
