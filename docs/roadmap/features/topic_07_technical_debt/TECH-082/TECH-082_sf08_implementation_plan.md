# Implementation Plan: Domain Logic Lives in the Flow Engine [SF-08: One boundary rule]
- **Feature ID**: TECH-082
- **Sub-Feature**: SF-08 — One boundary rule
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-08
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf08_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-03)

## Scope

FR-15 (the rule, once, in a pure resolver; the spec says it) and FR-21 (SpecWeaver's own tree obeys
it, checked by a guard that uses the same resolver). AD-9: the resolver lives in `assurance/graph`
beside `topology.py`. AD-12: `widens` keys use the `consumes` path form. SF-09 later feeds the
resolver to the product check in all 9 languages; this SF does not touch any language checker.

## The rule, as the resolver applies it

For a folder with a manifest, with parent manifest P (nearest ancestor that has one):

1. **Effective forbids** = own `forbids` ∪ P's effective `forbids`.
2. Each own `consumes` entry must be one of: inside P's effective `consumes` (P's own `consumes`
   plus P's own `widens` keys); a sibling (inside P's own folder); or a key of own `widens`.
3. No own `consumes` entry may overlap an effective `forbids` entry (inside it, or containing it)
   unless a `widens` key covers it.
4. Each `widens` entry needs a non-empty reason, and must widen something (rule 2 or 3 would fail
   without it); otherwise it is refused as empty or stale.
5. A folder without a manifest takes its nearest ancestor's effective rule. A top manifest (no P)
   is judged by its own lists only.

The resolver returns, per manifest folder, its effective rule and a list of breaches
(`wider`, `uses-forbidden`, `empty-reason`, `stale-widens`), each naming the folder, the entry and
the parent folder. It also answers `allows(folder, target) -> bool`, which SF-09 uses per import.

## Decisions (Phase 4, the user 2026-11-03)

- **D-1 How each breach is fixed** `[agreed 2026-11-03]`: the parent's own code may use it too →
  add it to the parent's `consumes`; the parent must not use it (archetype or `forbids`) → the
  child's `widens`, with a reason. The 18 manifests measured 2026-11-03:

| Manifest | Entries beyond its parent | Fix |
|---|---|---|
| `assurance/standards/interfaces` | `interfaces/cli_kit`, `interfaces/run_doors`, `core/flow` | Widen: the `sw standards` commands |
| `assurance/validation/interfaces` | `cli_kit`, `run_doors`, `core/flow`, `graph/lineage`, `workspace/project`, `sandbox/execution` (parent forbids `sandbox/*`) | Widen: the `sw check` / `sw drift` commands; `sandbox/execution`: `cli_drift.py:15` runs git through `SubprocessExecutor` |
| `core/config/bootstrap` | `core/flow/store`, `infrastructure/llm`, `workspace`, `workspace/memory` | Widen: bootstrap wires the stores and the model; `core/config` stays pure |
| `core/config/interfaces` | `cli_kit`, `assurance/validation/io`, `telemetry_logger` | Widen: the `sw config` commands |
| `core/flow/engine`, `handlers`, `run_state` | `commons`; `sandbox` (whole; parent lists 7 sandbox parts and forbids `sandbox/*/interfaces`); `workspace` (whole); `workspace/ast` | Narrow each child's `sandbox` and `workspace` to the parts it imports (grep at dev time); add `commons` and any part the area shares to `core/flow`'s `consumes` |
| `core/flow/interfaces` | `cli_kit`, `run_doors`, `workspace/analyzers` | Widen: the `sw run` commands |
| `graph/core/builder`, `engine`, `store` | `commons`; builder also `workspace/ast/adapters` | Parent: `graph/core` lists both |
| `graph/interfaces` | `cli_kit`, `assurance/graph`, `core/config` (parent forbids it) | Widen: the `sw graph` commands; `core/config`: `cli.py:154,178` read the config DB path |
| `infrastructure/llm/interfaces` | `cli_kit` | Widen: the `sw llm` commands |
| `workflows/drafting/interfaces` | `cli_kit`, `run_doors`, `core/flow`, `interfaces/cli` | Widen: the `sw draft` commands |
| `workflows/implementation/interfaces`, `workflows/review/interfaces` | `cli_kit`, `run_doors`, `core/flow`, `workspace/project` | Widen: their `sw` commands |
| `workspace/project` | `graph`, `assurance/graph` | Widen: `sw scan` builds the topology; `workspace` (a store) does not |
| `workspace/project/interfaces` | `cli_kit` (grandparent `workspace` forbids `interfaces`), `workspace/store` | Widen: the `sw init`/`sw scan` commands; `workspace/store` too |

- **D-2 Overlap counts both ways** `[agreed 2026-11-03]`: a `consumes` entry inside a forbidden
  path, or containing one, is a breach unless `widens` covers it (rule 3).
- **D-3 Two `consumes` forms**: SpecWeaver's manifests write paths (`specweaver/sandbox`); the
  product's `TopologyGraph` (`topology.py:117-123`) and `sync_tach_toml` (`tach_sync.py:41-47`)
  read an entry as another manifest's `name`. The resolver turns each entry into a folder: equal to
  a manifest `name` → that folder; otherwise a path (`/` or `.` separated, trailing `*` dropped).
- **D-4 `TopologyNode.widens: dict[str, str]`**, read at `topology.py:226`. A `widens` that is not a
  map is a load warning and counts as empty, so rule 4 refuses its entries instead of the loader
  crashing.
- **D-5 The guard also ties tach to the rule**: each `tach.toml` `depends_on` target must be allowed
  by the resolver for that module's folder.

> [!CAUTION]
> **As built (CB-1)**: the guard uses `topology.load_nodes`, split out of `from_project`, because
> `from_project` also hashes every source (`_calculate_stale_seeds`).
> The guard must never call `TopologyGraph.from_project` with the default.
> The default `auto_infer=True` WRITES a `context.yaml` into every folder without one
> (`topology.py:244-276`). Before the first run, read `_calculate_stale_seeds` and confirm it only
> reads its cache.

> [!WARNING]
> `TopologyGraph` keys nodes by `name`, so two manifests with one name silently drop one. Our tree
> has no duplicate today (checked 2026-11-03). The guard asserts the loaded node count equals the
> number of `context.yaml` files, so a future clash fails loudly.

## Path List rows this SF owns

| Row | Interface first exists | Test |
|---|---|---|
| P-12 our tree → guard → resolver | CB-2 (the resolver exists after CB-1, the manifests are not yet fixed) | `tests/unit/test_boundary_rule_holds.py`, red with the 18 breaches, green after the fixes |

## Commit Boundaries

### CB-1 (interior): the resolver and the spec — FR-15

**Red first**:

1. `tests/unit/assurance/graph/test_boundary_rule.py` (`Proves: TECH-082 FR-15`), red today (no
   module). 4 buckets:
   - happy: a child inside its parent's `consumes` passes; a parent's `forbids` reaches a
     grandchild; a sibling is not a widening; a declared widening passes and lifts an inherited
     forbid for that path only.
   - boundary: a folder without a manifest takes its ancestor's rule; a glob forbid
     (`sandbox/*/interfaces`); a top manifest is judged alone; name-form and path-form entries (D-3).
   - degradation: an empty manifest; a `widens` that is a list, not a map (D-4); a manifest
     whose parent manifest has no `consumes` key.
   - hostile: an empty reason; a stale `widens`; a broad entry containing a forbidden part (D-2);
     `..` or an absolute path in an entry is refused as naming no folder.
2. `tests/unit/assurance/graph/test_topology.py` (existing file): a manifest's `widens` is loaded.
3. `tests/integration/assurance/graph/test_boundary_rule_from_manifests.py`
   (`Proves: TECH-082 FR-15`): a temporary tree of real `context.yaml` files → `TopologyGraph`
   loads it → the resolver gives the expected breaches. Seam: loader → resolver.

**Green**: `assurance/graph/boundary_rule.py` (pure; no file access, takes loaded nodes);
`TopologyNode.widens`; `assurance/graph/context.yaml` and tach `expose` gain the new names;
`context_yaml_spec.md` §Context inheritance (lines 226-233) and the field table (lines 160-175)
say the rule and `widens`.

**Mutant** (`TECH-082_mutants.json`, FR-15): in the resolver, drop the parent's forbids from the
effective forbids (rule 1) → the grandchild test goes red.

### CB-2 (closes SF-08, HITL): our tree obeys it — FR-21

**Red first**: `tests/unit/test_boundary_rule_holds.py` (`Proves: TECH-082 FR-21`): load
`src/specweaver` with `TopologyGraph`, run the resolver, assert no breach; assert each tach
`depends_on` target is allowed (D-5); assert the loaded node count equals the manifest file count. Red today with the 18 manifests of D-1.

**Green**: edit the 18 manifests as D-1; each `widens` reason one line, naming what uses it.

**Done when**: the guard is green; `test_manifests_match_tach.py`, `test_context_yaml_paths_exist.py`
and `tach check` pass; this mutant is killed: delete the `sandbox/execution` entry from
`assurance/validation/interfaces/context.yaml`'s `widens` → the guard goes red.

**Gate**: `python scripts/tests.py cb TECH-082 --kind refactor`, `specweaver-pre-commit`, stage,
**STOP** for the user.

## Research Notes

- `TopologyNode` fields: `name, level, purpose, archetype, consumes, exposes, forbids, constraints,
  mcp_servers, consumes_resources, operational, yaml_path` (`topology.py:51-66`); loaded at
  `topology.py:215-231`; the loader skips a manifest without `name`.
- `TopologyGraph.__init__` warns on a `consumes` entry that is no node name (`topology.py:117-123`).
- `assurance/graph` is `pure-logic`; it forbids `sandbox/*`, `infrastructure/llm`,
  `workflows/drafting`, `workflows/implementation`; it consumes `workspace/context`, `graph`,
  `workspace/analyzers`.
- `test_manifests_match_tach.py`: covers = equal, or one is a dotted prefix of the other;
  `test_context_yaml_paths_exist.py:44-48` resolves an entry as a folder, a `.py` file or a glob.
- `workspace/store` is `src/specweaver/workspace/store.py` (a file module), not stale.
- 74 manifests; 50 nested under another; the 18 breaches come from
  `/tmp/claude-1000/-home-stevebula-projects-github-com-specweaver/d024f03a-2def-433c-89c4-b8471bece529/scratchpad/rule.py`
  (a throwaway measurement; the guard replaces it).

## Red/Blue (Phase 5), 2 cycles

- R1 (HIGH) The guard would call `TopologyGraph.from_project` with its default `auto_infer=True`,
  which writes `context.yaml` files into `src`. Fixed: the CAUTION under D-5.
- R2 (MEDIUM) Rule 2 did not say what a parent's effective `consumes` is. Fixed: own `consumes`
  plus own `widens` keys.
- R3 (MEDIUM) Nodes keyed by `name` drop a manifest on a clash. Fixed: the guard counts nodes
  against files.
- R4 (LOW) AD-12 says `widens` keys use the `consumes` form; D-3 allows both forms. Consistent:
  whatever form a project's `consumes` uses works in `widens`.
- R5 (LOW) Narrowing `core/flow/engine` to sandbox parts must still cover tach's whole
  `specweaver.sandbox` edge. Checked: `test_manifests_match_tach._covers` accepts a part as covering
  the whole.
- Cycle 2: challenged D-3 (could a manifest `name` equal a path, e.g. `graph`?) — the name match
  wins; in our tree no manifest is named like a path. Challenged the sibling rule against an
  inherited forbid — rule 3 still applies to siblings. No new finding above LOW.

## Backlog

None.
