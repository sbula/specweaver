# task.md — B-SENS-03 SF-03, CB-1: SQL reports one name per object

**Plan**: `docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf03_implementation_plan.md`
**Boundary**: CB-1 of 2 · **FR-7** · **Tier**: unit

## Test matrix

| Bucket | Story |
|---|---|
| **Happy path** | `CREATE TABLE public.orders` → **one** symbol `public.orders` · an unqualified `CREATE VIEW summary` → `summary` · `CREATE FUNCTION analytics.total()` → `analytics.total` · the **exact list** for a file holding all three |
| **Boundary/edge** | A quoted identifier `CREATE TABLE "my table"` · a three-part name `a.b.c` if the grammar allows it · an empty file |
| **Graceful degradation** | Unparseable SQL → no raise · `extract_symbol` on a name that is not there |
| **Hostile** | **Strict resolution** `[agreed 2026-08-26]`: `extract_symbol(code, "orders")` must NOT resolve when the symbol is `public.orders` · `extract_symbol(code, "public.orders")` must resolve |

**Anything else doing this job?** Yes — `extract_symbol` and `list_symbols` must agree about what a
symbol is called. They already share `_declared_names`; `_find_symbol_node` is the half that does
not, and it is the one moving.

## Tasks

- [x] **T1** — Red: `tests/unit/workspace/ast/parsers/sql/test_sql_qualified_names.py`
- [x] **T2** — Capture `object_reference` rather than its `identifier` children, all three rules
- [x] **T3** — `_find_symbol_node`: the name node **is** the `object_reference` now
- [x] **T4** — Update the characterization net's SQL literals, each with its reason inline
- [x] **T5** — Mutant: the capture reverts to `identifier`. Killed by the **exact-list** assertions

## Pre-commit phases

- [x] P1 arch · [ ] P2 test gap (HITL) · [ ] P3 implement (HITL)
- [x] P4 suite · [ ] P5 quality · [ ] P6 docs · [ ] P7 walkthrough · [ ] P7.5 red/blue (HITL)

## CB-1 done

2 mutants, 2 kills — after the second was **re-pointed**. It first aimed at a type guard in the SQL
parser that turned out EQUIVALENT: `_named_nodes` yields only `name` captures and this query
captures nothing but `object_reference`, so the guard can never be false. The guard was removed and
the mutant now targets `_named_nodes`' exact text match, which is what actually enforces strictness.

Corpus: 20 judged, 20 protected, 0 stale. Record: `B-SENS-03_sf03_cb1_walkthrough.md`

---

# CB-2 — Rust reports its trait members  (FR-18)

- [x] **T1** — Red: `tests/unit/workspace/ast/parsers/rust/test_rust_trait_members.py`
- [x] **T2** — `function_signature_item name: (identifier) @name` in the query
- [x] **T3** — `_get_symbol_scope`: both item types, and walk up for `trait_item` as well as `impl_item`
- [x] **T4** — Update the three Rust literals in the two nets, reasons inline
- [x] **T5** — Two mutants, because there are two causes: the query line, and the `trait_item` branch

## CB-2 done — SF-03 COMPLETE

3 mutants, 3 kills. Corpus: 23 judged, 23 protected, 0 stale.
Record: `B-SENS-03_sf03_cb2_walkthrough.md`
