# Walkthrough: TECH-081 SF-02 — The manifests tell the truth

Plan: [TECH-081_sf02_implementation_plan.md](TECH-081_sf02_implementation_plan.md).

## CB-1 — fields, phantoms and labels (FR-6, FR-8)

### What changed

- 32 manifests gained `name` (and `purpose` where missing), each written from the module's files and
  its existing `description`.
- Archetypes no spec defines were replaced: `interface` → `entry-point` (5 CLI modules), `workspace`
  → `store` (`workspace/store.py`), `core`/`domain` → `orchestrator` (the `graph/core` and
  `workspace/ast` containers), `raw-data` → `mixed` for `commons` (it still reads files; SF-03 makes
  it `pure-logic`). The five `graph` manifests and `sandbox/execution` gained one.
  `sandbox/web/interfaces` is now `adapter`: it calls `httpx.post`.
- Phantom `exposes`: `CodeGenerator` → `Generator`, `Selectors` → `ContextSelector`,
  `StandardsInferrer` removed.
- `sandbox/execution/context.yaml` used a nested `module:` schema; it is flat now.

### Red first

`tests/unit/test_manifests_are_complete.py`: missing fields (32 manifests), phantoms (3), and
`web/interfaces` as `orchestrator` failed before the edits. The archetype-set test was added after
the labels were fixed and proven by its mutant instead (`raw-data` back → red).

### Proof

Mutants, all OBJECTED: `phantom-expose-back`, `purpose-blank`, `unknown-archetype`,
`web-tool-orchestrator`.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) the `exposes` rule accepts any module-level `import` of the name, so a re-export
  counts. Blue: that is what a public surface is (`get_db` in `interfaces/cli`); a name nobody binds
  still fails.
- R2 (LOW) `commons` labelled `mixed` is an escape hatch. Blue: it is true today; SF-03's scope now
  says it becomes `pure-logic`.
- Cycle 2: no new finding.
