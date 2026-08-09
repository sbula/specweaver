# [Skill: specweaver-pre-commit] Phases 1–2 Combined Review — TECH-025 SF-04 CB-3

Scope: the citations and the orphan adoption — the boundary that turns TECH-001's ledger green.
CB-1 `f56bc7ef`, CB-2 `1a19e2f0`. Plus one carried-over tidy-up: `llm_database_coupling` folded
from two parses to one.

Comment inline under any row. Nothing proceeds to Phase 3 until you reply.

---

## Part 1 — Architecture Findings (deferred from Phase 1)

**No violations found.**

| Check | Result | Evidence |
|---|---|---|
| NFR-1 zero production change | Holds | `git status --porcelain -- src/` → 0 lines |
| Dependency direction | Clean | `tach check` → `All modules validated!` |
| Layer placement / archetype | N/A | Docs, three test docstrings, one test-helper refactor |
| **AD-4 waiver applied correctly** | Yes | Four delivered-story documents edited — TECH-001's design, its SF-01 and SF-02 plans. Each carries a dated note naming TECH-025 as the author. None gains scope |
| NFR-5 IDs confined to one line | Holds | `TECH-001` appears exactly **once** in each of the three test files — the `Proves:` line |

> Comment:

---

## Part 2 — Coverage Matrix

**Module: `tests/unit/test_architecture.py`** (the only logic change in this boundary)

| Class / Function | Unit | Integration | E2E |
|---|---|---|---|
| `llm_database_coupling()` — single-parse fold | ✅ | — | — |

**Documents changed** *(matrix required regardless — §2.4)*

| Change | Verified by |
|---|---|
| TECH-001 design: SF-01 gains FR-7, FR-8 | `check_fr_coverage.py TECH-001` |
| TECH-001 SF-01 plan: cites FR-1/2/3/7/8 | same |
| TECH-001 SF-02 plan: cites FR-4/5 | same |
| Three `Proves:` docstrings | same |

### The fold is behaviour-preserving, and that is asserted rather than assumed

Two `ast.walk` passes over an identical tree became one. Re-probed: reverting the body to the
substring check turns `test_a_word_that_merely_contains_database_is_not_a_coupling` red and nothing
else — the same single failure the pre-fold code produced under CB-2's probe Q4. Same guard, same
blast radius, so the refactor did not quietly widen or narrow the check.

### Vacuous-proof check (§2.5b)

Executable half: `quality.py cb --only useless_asserts,test_basenames` → **2 passed**, repo-wide.

The honest risk in this boundary is not a weak assertion — it is a **dishonest citation** (NFR-3).
Each was checked by reading the test body, not the name:

| FR | Cited test | Would it fail if the FR regressed? |
|---|---|---|
| FR-1 | `test_llm_store.py` | Yes — drives the store's models, constraints and session scope directly. Folding those tables back into the shared config DB breaks it |
| FR-2 | `test_flow_store.py` | Yes — same shape, against `ArtifactEvent` |
| FR-3 | `test_workspace_store.py` | Yes — same shape, against the profile models |
| FR-4 | `test_cli_commands_live_in_their_own_domains` | Yes — enumerated from the tree, floor of 9 |
| FR-5 | `test_every_domain_cli_is_mounted_on_the_root_app` | Yes — disk vs. `main.py`, probed under CB-2 Q1 |
| FR-6 | `test_sandbox_is_grouped_by_feature_not_by_layer` | Yes — absence of the flat split, plus a layer per feature |
| FR-7 | `test_config_modules_hold_no_domain_orchestration` | Yes — imports **and** import-time DB work, four synthetic probes |
| FR-8 | `test_llm_entry_points_take_settings_not_a_database` | Yes — AST-resolved, probed twice |

### 🟠 Finding C1 — the three store tests are cited but were never probed

FR-1/2/3's proofs are pre-existing tests I did not write and have not seen fail. Everything else in
this ledger was probed under CB-1/CB-2; these three were adopted on a reading. A citation is a
claim that the test would fail if the behaviour regressed, and for exactly these three that claim
currently rests on inspection alone.

Cheap to close: delete a uniqueness constraint or a column from one store model and confirm the
matching file goes red.

### 🟠 Finding C2 — nothing stops a future edit deleting a `Proves:` line

The ledger is green today and would go quietly red-then-unnoticed if a docstring were tidied away.
That is **SF-07's** job (`fr_traceability_closed.txt` + the guard test), and SF-07 depends on this
boundary. Recorded so the gap is visibly *scheduled* rather than missed.

> Comment:

---

## Part 3 — Proposed Test Stories

### Unit

| # | Story | Target |
|---|---|---|
| W1 | [Degradation] Probe the three adopted store proofs — break one model constraint per store and confirm the cited file, and only it, goes red | Closes C1 |

### Integration / E2E
None. This boundary adds no behaviour; the citations are verified by the FR gate, which is a script
run at closure rather than a pytest.

### §2.5a Mandatory challenge — is this set sufficient?

**Yes, with W1.** The temptation here is to treat "the gate exits 0" as the finish line — it is
precisely the failure this ticket exists to remove. The gate checks that a *string* appears in a
plan and a test; only NFR-3 checks that the test means it. Seven of the eight citations have been
probed as part of writing them. W1 covers the three that were adopted rather than written.

**Deliberately not proposed:** a guard against a deleted `Proves:` line (C2). It is SF-07's scope
and duplicating it here would mean two mechanisms for one idea.

> Comment:

---

## My recommendation

Run **W1**, then Phases 4–7.5. If any of the three store tests survives its probe, that citation is
fiction and must be replaced before the ledger is allowed to close — which is the entire thesis of
this ticket applied to its own work.

> Comment:

---

## W1 result — all three citations are genuine, and the first attempt was wrong

| FR | Defect planted in the store model | Cited test |
|---|---|---|
| FR-1 | `name` NOT NULL dropped (`llm/store.py`) | **1 failed** ✅ |
| FR-2 | `model_id` default `"unknown"` → `"CHANGED"` (`core/flow/store.py`) | **1 failed** ✅ |
| FR-3 | `root_path` UNIQUE dropped (`workspace/store.py`) | **1 failed** ✅ |

**C1 closed.** Each cited file observes its store's own model definition, so folding these tables
back into the shared config database — the regression FR-1/2/3 exist to prevent — cannot pass
silently.

**The first FR-2 probe survived, and that is worth keeping in the record.** Dropping `run_id`'s
NOT NULL changed nothing, and neither did dropping `event_type`'s. `test_flow_store.py`'s
degradation case omits a *different* required field, so those two constraints are unasserted. I had
picked a constraint the test does not exercise and briefly had evidence pointing the wrong way —
which is exactly why W1 was worth running rather than reasoning about.

Two consequences, stated separately because they are different claims:

1. **FR-2's citation stands.** Its claim is *"a standalone flow_store layer handles pipeline
   execution state"*, and the default-value probe shows the test reads that layer's own models.
2. **`test_flow_store.py`'s NOT NULL coverage is partial** — two of four columns. Not FR-2's claim,
   not this ticket's scope, and not a reason to hold the ledger. Recorded here so it is a known
   gap in a file this ticket touched rather than an undiscovered one.

Residue check after every probe: `git status --porcelain -- src/` → 0 lines.

> Comment:
