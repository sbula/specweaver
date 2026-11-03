# Walkthrough: TECH-082 SF-08 — One boundary rule

## CB-1: the resolver and the spec (FR-15)

**What changed**
- `assurance/graph/boundary_rule.py` (new, pure): `breaches(nodes, root)` and
  `allows(nodes, root, folder, target)`. Kinds: `wider`, `uses-forbidden`, `empty-reason`,
  `stale-widens`, `bad-entry`.
- `assurance/graph/topology.py`: `load_nodes(project_root)` holds the manifest reading that
  `TopologyGraph.from_project` did inline; it neither hashes nor infers. `TopologyNode.widens`.
- `context_yaml_spec.md`: §Context inheritance now states the rule; `widens` in the example and the
  field table. `known_boundary_violations.md`: the topology I/O row names `load_nodes`.

**Deviation from the plan**: the plan had the guard call `from_project(auto_infer=False)`. That still
hashes every source under the root (`_calculate_stale_seeds`). `load_nodes` was split out instead,
so the guard and SF-09 read manifests only. `from_project` behaves as before (its tests unchanged).

**Tests**: unit 31 (`test_boundary_rule.py` 25, `test_topology_widens.py` 7), integration 4
(`test_boundary_rule_from_manifests.py`). Full suite: 12043 passed, 9 skipped. `quality.py cb`
17/17, `quick` 9/9, `doc` 14/14.

**Mutants** (`TECH-082_mutants.json`, FR-15), all killed: forbids not inherited (5 tests object);
sibling counted as wider (1); stale `widens` accepted (1).

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `breaches` / `_Tree.judge` / `_judge_consumes` / `_kinds` | ✅ | ✅ | — (SF-09) |
| `allows` | ✅ | — | — (SF-09) |
| `_Tree.parts` (name, path, dotted, `..`, absolute, `\`) | ✅ | — | — |
| `_folder_of` (outside root, no path) | ✅ | — | — |
| `load_nodes`, `_widens_of` (map, list, scalar, empty value) | ✅ | ✅ | — |

**Edge cases added in Phase 3**: backslash entry; bad `forbids` and `widens` keys; a manifest outside
the root; `allows` with no manifest and with a bad target; a `widens` key with no value; a root-level
manifest whose own folder must not lift its `forbids`.

**Architecture**: the resolver imports only the standard library and, for typing, `topology`. No
new edge. The I/O in `topology.py` is the existing ledger row, now naming `load_nodes`.

**Red/blue (7.5)**
- R1 (HIGH, fixed) `allows` returned True for anything inside the manifest's own folder before
  checking `forbids`, so a root-level manifest's `forbids` never applied. Test first, then fixed.
- R2 (MEDIUM, accepted) `allows` builds the tree on every call. Fine for the guard; SF-09 calls it
  per import and must build the tree once (a note for SF-09's plan).
- R3 (LOW) recursion in `forbids` follows strictly shorter folders, so it ends.
- No decision needed from the user.

## CB-2: our tree obeys the rule (FR-21)

**What changed**
- `tests/unit/test_boundary_rule_holds.py` (new): no breach in `src/specweaver`; every `tach.toml`
  edge allowed; every manifest loaded; the check finds the manifests. Red first: 62 breaches,
  3 refused tach edges.
- 18 manifests fixed by D-1: `widens` with a reason on the 10 `interfaces` folders,
  `core/config/bootstrap` and `workspace/project`; `core/flow` and `graph/core` list what their
  children share; the 3 `core/flow` children narrowed `sandbox` and `workspace` to the parts they
  import.
- `boundary_rule._overlap`: a `consumes` entry "contains" a forbidden path only when it is literally
  above it. `core/flow`'s `sandbox/dispatcher` (a file) was refused against `sandbox/*/interfaces`,
  though only a glob could reach it. Test first (`test_an_entry_a_forbid_glob_only_might_reach…`).

**Choices made without a stop (for the user's review)**
1. 5 `consumes` entries were used by no import and no tach edge, so they were **removed**, not
   widened: `drafting/interfaces` → `interfaces/cli`; `implementation/interfaces` and
   `review/interfaces` → `workspace/project`; `workspace/project` → `graph`;
   `workspace/project/interfaces` → `workspace/store`. Removing only narrows; a `widens` reason for
   an unused allowance would be false.
2. `workspace/project/interfaces` now widens `graph` (`cli.py:295` imports the graph engine); it was
   covered by its parent's unused entry before.
3. The overlap refinement above, within D-2.
4. The guard treats a tach edge to a whole module (`sandbox`) as allowed when the part the manifest
   consumes (`sandbox/execution`) is allowed: tach modules are coarser than manifest entries.

**Tests**: full suite 12049 passed, 9 skipped; `cb` 17/17; `doc` 14/14; all 7 boundary guards pass
(`tach check` inside `test_architecture.py`). `stale_mutants.py`: 0 stale in 53 corpora.

**Mutant** (FR-21): comment out `sandbox/execution` in `validation/interfaces`' `widens` → 2 guard
tests object. Recorded in `TECH-082_mutants.json` (no `symbol_sha`: YAML, as TECH-081's).

**Red/blue (7.5)**
- R1 (MEDIUM, accepted) a reason is prose; nothing proves it true. The rule requires one; review
  judges it.
- R2 (LOW, accepted) the coarse tach-edge match could excuse a forbidden use of another part of the
  same tach module; SF-09's per-import check judges real imports.
- R3 (LOW, fixed) the guard's owner lookup raised `StopIteration` for a one-file tach module; it now
  returns "not allowed".
