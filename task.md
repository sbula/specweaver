# Task: TECH-068 — the two open gate findings

**Skill**: `specweaver-dev` · **Story**: TECH-068 (`🟡`, open) · **Kind**: bugfix
Both are declared FRs of an open ticket that were never fully built. No new ticket.

## Research (done, measured — do not re-derive)

| Fact | Evidence |
|---|---|
| `GraphEdge` has **no** metadata field | `models.py` — `source_hash`, `target_hash`, `kind`, nothing else |
| `upsert_edge` writes only `EDGE_KIND_ATTR` | `core.py` — so nothing can reach `graph_edges.metadata`, which the store already reads |
| The 2 KB cap is hard-coded in `GraphNode` | `models.py:39` — `if payload_size > 2048` |
| Go embedding is detectable | struct: `field_declaration` with a `type_identifier` and **no** `field_identifier`. interface: `type_elem > type_identifier` |
| Go has **no** syntactic `implements` | interface satisfaction is structural and implicit — nothing in the AST expresses it |
| Rust distinguishes both cleanly | `impl_item` with `for` → implements; `trait_item > trait_bounds` → extends; `impl_item` without `for` → inherent, nothing |
| Rust's declared name is **not** the first identifier | `impl Runner for Impl` — the subject is the SECOND `type_identifier`. `_declared_type_name` would pick `Runner` |
| One Rust type appears in several nodes | `struct Impl;` and `impl Runner for Impl` both name `Impl`; the base `extract_supertypes` **overwrites**, so one clobbers the other |
| Go types are classified as procedures today | `extract_framework_markers` returns `{}` for Go, so the adapter's `is_class` is false and `_index_types` never sees them — a Go supertype could only ever ghost |
| Rust already half-reports it | markers give `Impl: extends: [Runner]` — flattened, kinds lost. That is the gap `FR-4` exists to close |

## Tasks

- [x] 1 — `GraphEdge` gains `metadata`; `upsert_edge` writes it — `models.py`, `core.py` / `test_edge_metadata.py`
- [x] 2 — Mapper puts the unresolved raw name on every ghost edge (imports, supertypes, calls) — `mapper.py` / `test_ghost_raw_names.py`
- [x] 3 — The raw name is capped so a pathological identifier cannot abort a build (`NFR-5`, `NFR-6`) — `mapper.py`, `models.py`
- [x] **CB-1 — FR-12: an unresolved target says what it was**
- [ ] 4 — `extract_supertypes` MERGES per name instead of overwriting — `base.py` / `test_supertypes.py`
- [ ] 5 — Go reports struct and interface embedding as extension — `go/codestructure.py` / `test_go_supertypes.py`
- [ ] 6 — Rust reports `impl T for X` as implementation and `trait A: B` as extension — `rust/codestructure.py` / `test_rust_supertypes.py`
- [ ] 7 — The contract test names every shipped parser explicitly, so an empty result is a declared exemption rather than a loop that never runs — `test_every_parser_answers_the_contract.py`
- [ ] **CB-2 — FR-4: every language answers the supertype contract**
- [ ] 8 — The adapter treats a declared type as a type, so Go and Rust types are indexable targets — `graph_adapter.py` / seam tests
- [ ] 9 — Go and Rust hierarchies resolve to real nodes in a real build — integration + e2e
- [ ] **CB-3 — FR-9 / FR-10: the hierarchy is traversable in every language**

## Decisions taken with the user

- `T-SPEND`, `T-BOUNDARY`, `T-POSTURE`, `T-DIVERGE`, `T-ORDER`, `T-UNDO`, `T-DATA`, `T-OBLIGATION`: not touched
- `T-SCOPE`: fired — the user said "do the two open findings" after being shown both at the §2.8 gate
- `T-PROVEN`: not touched — closing TECH-068 stays the user's call
- `T-NAME`: fired — Go embedding emits `EXTENDS`, not a tenth `EdgeKind`. Chosen by the user
  2026-08-22 over `EMBEDS`: the ontology already defines `EXTENDS` as "A is built from B", and a
  tenth kind is `T-ARCH` for every reader, including the ones not built yet
- `T-ARCH`: not touched — the ontology stays at nine kinds
- `T-DEFAULT`: not touched — the raw-name cap reuses `RT-25`'s agreed 2 KB rather than introducing a number
