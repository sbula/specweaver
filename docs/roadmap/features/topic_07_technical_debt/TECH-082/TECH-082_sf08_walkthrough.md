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
