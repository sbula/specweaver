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

## CB-2 — the manifests match `tach.toml` (FR-4, FR-7) — closes SF-02

### What changed

- One schema: the six `graph/**` manifests (`module_name`, `layer`, `allowed_imports`,
  `forbidden_imports`) now use `consumes`/`forbids` (AG-15, moved here from `TECH-080`
  `[agreed 2026-10-27]`); five CLI manifests renamed `exports` → `exposes` and lost the unread
  `dependencies` list; `workspace` lost its nested `dependencies: {allowed, forbidden}`; entries
  spelled `src.specweaver.*` (which `test_context_yaml_paths_exist.py` skipped) are real paths now.
- `consumes` now covers every plain `tach.toml` edge (63 entries over 22 manifests). `deprecated`
  edges stay out: they are owed in the ledger.
- Seven new manifests: `sandbox`, `workflows/scenarios`, `workflows/evaluators`, `workspace/memory`,
  `core/flow/engine` (its `forbids: core/flow/handlers` states FR-11's goal), `core/flow/handlers`,
  `graph/lineage`.
- `graph` forbade `specweaver/config` (moved); it forbids `specweaver/core/config` now.
  `assurance/graph` was also named `graph`; it is `assurance-graph`.
- `test_declared_imports.py` (TECH-068 AD-3) reads `consumes`; the AD-3 comment stays beside it.

### Red first

`tests/unit/test_manifests_match_tach.py`: 7 modules without their own manifest, 63 undeclared
edges, 6 missing manifests — all red before the edits.

### Proof

Mutants, all OBJECTED: `consumes-entry-dropped`, `forbid-what-tach-allows`, `manifest-emptied`
(this one first came back SILENT: a manifest with its `name` line gone still counted as present;
the test now requires a `name`).

### Gate notes

Full suite 11816 passed, 9 skipped (one corpus-load failure fixed: a mutant's `new` may not be
empty); `quality.py cb`, `doc`, `tach check` green.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) the round-trip rewrite dropped one inline comment on `core/flow`'s llm entry. Blue: it
  said "pure logic modules must not depend on LLMs" on a module that does; it was wrong.
- R2 (MEDIUM) `consumes` lists are wider than `tach.toml` in places (`graph` consumes `sandbox`).
  Blue: a manifest may allow more than is used; FR-4 checks only that nothing used is undeclared.
- Cycle 2: no new finding.
