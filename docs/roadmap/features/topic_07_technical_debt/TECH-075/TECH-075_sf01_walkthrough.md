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
