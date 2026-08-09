# [Skill: specweaver-pre-commit] Phases 1–2 Combined Review — TECH-025 SF-04 CB-2

Scope: the five structural invariants in `tests/unit/test_architecture.py` (+209 lines, 12 new
tests). CB-1 is committed (`f56bc7ef`); this boundary answers *is TECH-001's claim true?* The
ledger stays RED until CB-3 links it.

Comment inline under any row. Nothing proceeds to Phase 3 until you reply.

---

## Part 1 — Architecture Findings (deferred from Phase 1)

**No violations found.**

| Check | Result | Evidence |
|---|---|---|
| Layer placement | N/A | One file changed, under `tests/`. Zero `src/` (NFR-1) |
| Dependency direction | Clean | `tach check` → `All modules validated!` |
| Circular imports | Clean | Only `ast` + `pathlib`, both already imported by the file |
| Parallel mechanisms (1.4) | Correct home | `tests/unit/test_architecture.py` already holds this repo's structural invariants and already carries TECH-001 FR-9's citation. Plan R5 |
| Archetype / `context.yaml` | N/A | Test tree |
| File size | 384 lines | Under the ceiling |

> Comment:

---

## Part 2 — Coverage Matrix

**Module: `tests/unit/test_architecture.py`** (the assertion helpers are the logic under test)

| Class / Function | Unit | Integration | E2E |
|---|---|---|---|
| `domain_cli_modules()` | ✅ | — | — |
| `unmounted_domain_clis()` | ✅ | — | — |
| `sandbox_layer_violations()` | ✅ | — | — |
| `config_orchestration_offenders()` | 🟡 | — | — |
| `llm_database_coupling()` | 🟡 | — | — |
| **The five live-tree assertions** | ❌ | — | — |

### 🔴 Finding B1 — four of the five live-tree tests can pass against a tree that does not exist

This is the headline and it is measured, not suspected. Every helper was called with
`Path("C:/nonexistent/tree")`:

| Helper | Real tree | Bogus tree | Vacuous? |
|---|---|---|---|
| `domain_cli_modules` | 9 | 0 | **no** — the `>= 5` assertion catches it |
| `unmounted_domain_clis` | `[]` | `[]` | **YES** |
| `sandbox_layer_violations` | `([], [])` | `([], [])` | **YES** |
| `config_orchestration_offenders` | `[]` | `[]` | **YES** |
| `llm_database_coupling` | `[]` | `[]` | partly — the test's *second* assertion reads `factory.py` and would raise, so the test as a whole is guarded |

So `test_every_domain_cli_is_mounted_on_the_root_app`,
`test_sandbox_is_grouped_by_feature_not_by_layer` and
`test_config_modules_hold_no_domain_orchestration` would each stay green if `SRC_ROOT` resolved to
nothing at all — a moved test file, a renamed `src/` layout, a `parent.parent.parent` off by one.

The plan anticipated exactly this class ("an absence proof that has never been observed failing is
indistinguishable from one that CANNOT fail") and answered it with synthetic `tmp_path` probes.
Those probes are good and they work — but they prove the **logic**. Nothing proves the **live
invocation is pointed at anything**. The seven synthetic tests would all still pass with `SRC_ROOT`
broken, because they never use it.

`domain_cli_modules`' `>= 5` is therefore load-bearing far beyond its apparent weakness: it is
currently the only thing tying any of this to the real repository.

### 🟠 Finding B2 — `config_orchestration_offenders` implements half of what the plan specifies

Plan §3 (FR-7 row): *"contain no orchestration — **no domain imports, no DB bootstrapping**"*. The
implementation checks imports only. `core/config/` has 6 top-level modules including
`database.py`, and the FR-7 claim as researched was that `database.py` imports only stdlib and
SQLAlchemy — which the import check does cover. But "no DB bootstrapping" is a separate assertion
that was specified and not written, and the test's docstring ("Configuration declares; it does not
orchestrate") claims the broader thing.

Either write it or narrow the docstring. Silently claiming the wider guarantee is the failure mode
this whole ticket exists to remove.

### 🟠 Finding B3 — `llm_database_coupling` matches a bare substring

`"Database" in f.read_text()` also fires on `DatabaseError`, on the word in a comment, and on
`# no Database here`. False positives fail loudly, so this is safe rather than wrong — but the
inverse matters more: a coupling reintroduced as `db: Any` or `session_factory` passes clean. The
same applies to `"SpecWeaverSettings" in ...`, which a comment satisfies.

An `ast`-based check is available — the file already imports `ast` and uses it three functions up.

### Vacuous-proof check (§2.5b)

Executable half: `quality.py cb --only useless_asserts,test_basenames` → **2 passed**, repo-wide.

| Pattern | Verdict |
|---|---|
| 1 Ambiguous exit code | Absent |
| 2 Stubbed-away subject | Absent — helpers run against real trees |
| 3 **Never executed** | **Unverified.** Written pre-reboot; no red-then-green record exists. Same standard I applied to CB-1: this needs a probe before sign-off |
| 4 Inert fixture input | Absent — `_plant()` writes real files that the helpers then read |
| 5 Escaped mock | N/A |
| 6 Assertion weaker than the name | **Two hits.** B1 (three tests pass on a nonexistent tree) and the `>= 5` threshold in a test named "CLI commands live in their own domains" — four domains could lose their CLI and it stays green |
| 7 Self-referential expectation | Absent — expected values are literals |

> Comment:

---

## Part 3 — Proposed Test Stories

### Unit

| # | Story | Target | Rationale |
|---|---|---|---|
| V1 | [Hostile] Every helper reports a **non-empty** view of the live tree — 9 CLI modules, ≥1 config module, a real `sandbox/`, both LLM entry points present. One test, and it is what ties the other four to reality | all five helpers | Closes B1 |
| V2 | [Boundary] Decide `>= 5`: either assert the enumerated count the tree actually has, or assert the decentralisation claim directly | `test_cli_commands_live_in_their_own_domains` | Closes the second half of B1's pattern-6 hit |
| V3 | [Hostile] `config_orchestration_offenders` detects DB bootstrapping, not only domain imports — or the docstring narrows to what it checks | `config_orchestration_offenders()` | Closes B2 |
| V4 | [Hostile] `llm_database_coupling` resolves `Database` as a real import/name via `ast`, so `DatabaseError` and a mention in a comment do not fire, and `db: Any` is not a way through | `llm_database_coupling()` | Closes B3 |

### Integration / E2E
None. These are structural invariants over the source tree; there is no seam and no user workflow.
Running them at another tier would be the same assertions with more ceremony.

### §2.5a Mandatory challenge — is this set sufficient?

**V1 is the one that matters.** Without it, three of the five proofs this boundary exists to write
are ornamental, and — worse — CB-3 is about to attach `Proves: TECH-001 FR-N` citations to them.
That would close a ledger against tests that cannot fail, which is *precisely* the fiction TECH-025
was opened to remove. Shipping CB-2 without V1 would make this ticket commit the offence it audits.

**V2 and V3 are honesty repairs**, cheap, and both are cases of an assertion claiming more than it
checks.

**V4 is the most optional.** The substring check cannot produce a false green for the coupling that
actually existed (`Database` was imported by name), so it guards today's claim correctly. It is
weak against a *future* reintroduction wearing a different name. I would take it, but I would not
block on it.

**Deliberately not proposed:** hard-coding the nine CLI module names. Plan Q3 is explicit that a
fixed list passes the day someone deletes the module *and* its entry, and V1 gets the same
protection from a count without the brittleness.

> Comment:

---

## My recommendation

Implement **V1, V2, V3** in Phase 3; **V4** if you want the stronger guard. Then probe all five
live-tree tests — break `SRC_ROOT`, and separately plant a violation of each invariant in the real
tree via `tmp_path` copies — because none of these twelve tests has ever been observed failing.

> Comment:
