# [Skill: specweaver-pre-commit] Phases 1–2 Combined Review — TECH-025 SF-04 CB-1

Scope of this boundary: the selector fix only — `scripts/tests.py` +
`tests/unit/scripts/test_tests_runner.py`. CB-2's five invariants are stashed out of the tree so
they cannot flatter this gate.

Comment inline under any row. Nothing proceeds to Phase 3 until you reply.

---

## Part 1 — Architecture Findings (deferred from Phase 1)

**No violations found.**

| Check | Result | Evidence |
|---|---|---|
| Layer placement | N/A | Zero files under `src/specweaver/`. NFR-1 forbids it; `git status` shows `scripts/` + `tests/unit/scripts/` only |
| `consumes` / `forbids` | N/A | `scripts/` has no `context.yaml` — build tooling, not a bounded context |
| Archetype compliance | N/A | Same reason |
| Dependency direction | Clean | `tach check` → `All modules validated!` |
| Circular imports | Clean | No `import` added. `_tier_relative` / `_scoped_paths` use `pathlib` only |
| Parallel mechanisms (1.4 zoom-out) | No duplication | `_scoped_paths()` is an **extraction** of the scope branches already inside `paths_for`, not a second mechanism. Both the source- and test-derived relatives now run the *same* function — which is the point: one place decides what a scope means |
| Common closure (1.6) | Single module | One file changed. Nothing to co-locate |
| Stability direction | N/A | No module dependency added |
| File size | 585/600 | `tests.py` grew 91 lines net and stays under the ceiling — but see the finding below |

### Finding A1 — `tests.py` is at 585/600 and this ticket keeps feeding it

Not a boundary violation; a trajectory. SF-01 pulled it back from exactly 600 by extracting
`_story_resolution.py`, and CB-1 has now spent 47 of the 62 lines that bought. The plan's own
§Finding says the root cause — *`paths_for` was built assuming every change is source-shaped* — is
recorded for its own ticket at TECH-025's closure. **Recommendation: leave the extraction to that
ticket rather than doing a third rider here**, but the number should be visible now rather than
discovered at 601.

> Comment:

---

## Part 2 — Coverage Matrix

**Module: `scripts/tests.py`**

| Class / Function | Unit | Integration | E2E |
|---|---|---|---|
| `_tier_relative()` | 🟡 | — | — |
| `_scoped_paths()` | 🟡 | — | — |
| `paths_for()` — test-derived branch | ✅ | — | — |
| `paths_for()` — source-derived branch | ✅ | — | — |
| `run_selections()` — BLOCKED message | ❌ | ❌ | — |

### Why the 🟡 / ❌ cells are what they are

- **`_tier_relative()` 🟡** — the prefix guard and the happy path are covered. The **`suffix != ".py"`
  guard is not.** `test_non_source_changes_select_nothing` looks like it covers this and does not:
  `README.md` fails the *prefix* check and never reaches the suffix check. A changed
  `tests/unit/fixtures/some.yaml` exercises a branch no test has run (story U1).
- **`_scoped_paths()` 🟡** — `touched`, `module` and `domain` are each covered from both the source
  and test side. The `raise UsageError(f"unknown scope ...")` line has **no test at all** — it had
  none before the extraction either, so this is inherited, and the fix-inherited-failures rule says
  it is mine now (story U2).
- **`run_selections()` BLOCKED ❌** — I rewrote the operator-facing message and **nothing asserts
  it.** `run_selections` has no test in this file at any tier. The message is the entire user
  experience of the bug this boundary fixes: someone hitting `selected NO tests` reads that text to
  decide whether they have a coverage hole or a selector hole. Rewriting untested prose is cheap;
  it is also how the old, wrong message survived (story U3).

### Finding A2 — the tier-root case is unpinned, and CB-2 lands on it

`tests/unit/test_architecture.py` has `rel.parent == "."`, so `module` scope resolves it to
`tests/unit` — **the whole tier**. That is defensible (a repo-root architecture test really does
cover the tier) but it is a 6000-test consequence of a `Path(".")`, asserted by nothing. CB-2's only
changed file is exactly this shape, so the next boundary's gate depends on behaviour this boundary
introduced and never pinned (story U4).

### Vacuous-proof check (§2.5b)

Executable half: `quality.py cb --only useless_asserts,test_basenames` → **2 passed, repo-wide.**

Manual half — every test in `TestScopeResolution` was read, not name-matched:

| Pattern | Verdict |
|---|---|
| 1 Ambiguous exit code | Absent. Assertions are on returned path lists |
| 2 Stubbed-away subject | Absent. `paths_for` runs against the real repo tree with the real default `repo_root` |
| 3 Never executed | **Unverified — this is the gap.** The seven new tests were written and passed on first run; I have no red-then-green record for them, because the reboot lost that session. See the probe note below |
| 4 Inert fixture input | Absent. The inputs are `Path` literals consumed directly |
| 5 Escaped mock | N/A — no mocks |
| 6 Assertion weaker than the name | **One hit.** `test_a_changed_test_does_not_leak_into_another_tier` asserts `== []`, which also passes if `_tier_relative` returned `None` for *every* input. Its sibling `test_a_changed_e2e_test_maps_to_its_domain` feeds the same path and asserts a non-empty result, so the pair is sound — but only as a pair, and nothing says so |
| 7 Self-referential expectation | Absent. Expected values are literal paths, not derived from the function |

**Probe (mandatory) — NOT yet performed for this boundary.** Per the skill's no-reliance-on-past-runs
rule I am not counting whatever the pre-reboot session may have done. This is the one item I will
not sign off without; it belongs in Phase 3.

> Comment:

---

## Part 3 — Proposed Test Stories

### Unit

| # | Story | Target | Source Line |
|---|---|---|---|
| U1 | [Hostile] A changed non-Python file *under the tier root* (`tests/unit/fixtures/x.yaml`) selects nothing — exercises the suffix guard that `README.md` never reaches | `_tier_relative()` | `tests.py:363` |
| U2 | [Hostile] An unknown scope raises `UsageError` — inherited untested, now in a function I extracted | `_scoped_paths()` | `tests.py:390` |
| U3 | [Degradation] The BLOCKED message distinguishes the two causes: a tests-only change that resolves nowhere vs. source with no mirror | `run_selections()` | `tests.py:470-478` |
| U4 | [Boundary] A test at the tier root resolves to the whole tier at `module` scope | `paths_for()` | `tests.py:408-416` |

### Integration
None proposed. `paths_for` already runs against the real on-disk tree in every test above — a
separate "integration" tier for a pure path function would be the same assertions with more
ceremony.

### E2E
None proposed. `tests.py` is developer tooling invoked by the commit gate, not a user-facing
workflow; there is no `sw` command to drive.

### §2.5a Mandatory challenge — is this set sufficient?

**U3 is the one I would insist on.** Everything else pins a branch; U3 pins the *reason the boundary
exists*. The plan's §CB-1 says the gate refused SF-04 with a message that was **false** — "you
changed source that nothing mirrors", when no source had changed. I replaced that text and no test
reads it. If the replacement is also wrong, the next person to hit this hits the identical wall,
and the identical rider gets written a third time.

**U4 is second, because CB-2 depends on it** (Finding A2). Cheap: one assertion.

**U1 and U2 are branch completion.** Both are real uncovered lines, both are three-line tests, and
U2 is inherited debt that landed in my extraction.

**Not proposed, deliberately:** a test that the union can never *remove* a source-derived module.
It is structurally impossible — `found |= ...` — and a test asserting that a set-union unions would
be testing Python, not this code. `test_source_and_test_changes_union_their_modules` already covers
the direction that can actually break (a test contributing where a source file also contributes).

> Comment:

---

## My recommendation

Implement **U1, U2, U3, U4** in Phase 3 — roughly 30 lines of test, and U3 is the only one needing a
new fixture (capturing `run_selections`' output). Then run the **probe**: break `_tier_relative`'s
prefix check and confirm exactly the test-derived assertions go red while the source-derived ones
stay green. Without that probe, seven of this boundary's tests have never been observed failing.

Do **not** extract `tests.py` further here (Finding A1) — that is the closure-time ticket's work.

> Comment:

---

# Phase 7.5 — Red/Blue Adversarial Review (CB-1)

Phases 3–7 are complete: 408 passed, `quality.py doc` 3/3, four probes all biting, walkthrough
written. The adversarial pass then found **two defects in the change itself**. Both are in the
`domain` scope, which none of U1–U4 touched.

## 🔴 R13 — the fix is incomplete for root-level e2e tests (CRITICAL)

A changed test directly under `tests/e2e/` contributes **nothing**:

```
tests/e2e/test_cli_bootstrap_e2e.py  ->  rel = "test_cli_bootstrap_e2e.py"
                                          rel.parts[0] = "test_cli_bootstrap_e2e.py"   (a file, not a domain)
                                          no such directory  ->  []
```

Verified against a real profile — `INT-US-21` at `cb`, only that file changed:

| tier | scope | selected |
|---|---|---|
| integration | all | `tests/integration` |
| e2e | **domain** | **`[]` → tier marked failed** |

**This is the same defect class CB-1 exists to remove**, one tier over. Four files are affected:
`test_cli_bootstrap_e2e.py`, `test_cli_decentralized_e2e.py`, `test_logging_e2e.py`,
`test_polyglot_validation_e2e.py`. Editing any of them in an INT story fails the gate for a reason
that is not the developer's fault. The new message even sounds plausible while being useless — *"the
tests you changed sit in a package with no mirror in this tier"* — the "package" is the tier root.

**Fix:** at `domain` scope, a test-derived relative with no directory part should resolve to
**itself** (the same answer `touched` already gives).

## 🟠 R12 — capabilities tests resolve one level too coarse (MINOR)

Same domain scope, opposite direction — too wide rather than too narrow:

| Changed | Selects |
|---|---|
| `tests/e2e/capabilities/core/test_lineage_e2e.py` | `tests/e2e/capabilities` — **every** capability |
| `src/specweaver/core/flow/runner.py` (same domain, source route) | `tests/e2e/capabilities/core`, `tests/e2e/core` — precise |

`rel.parts[0]` is `"capabilities"`, not the domain. **Safe** — union-only means this widens and can
never hide a test — but the two routes disagree about what "domain" means, and the asymmetry will
read as a bug to whoever meets it next. **Fix:** drop a leading `capabilities/` before taking
`parts[0]`.

## ✅ Attacks that found nothing

| # | Attack | Result |
|---|---|---|
| R2 | A root-level *unit* test (`tests/unit/test_logging_rollout.py`) drags in the whole tier | Correct — `rel.parent` is `.`, and a root-level test is not scoped to a module. Pinned by U4. Costs a full-tier run at `cb`, which is the honest answer |
| R5 | `tests/unit/conftest.py` → whole tier | Correct — a root conftest does affect everything |
| R14 | `tests/unit/graph/__init__.py` → `tests/unit/graph` | Harmless |
| R7 | A pure-docs boundary still selects nothing | Correct, and by design: `--kind audit` declares no tiers and is the intended route |
| R8 | `UsageError` mid-loop leaving partial state | None — raises before any return |
| R11 | Source + its mirroring test both changed at `touched` → duplicate paths | Deduped by the set |
| — | Path traversal via `changed` | Not reachable; `changed` comes from `git diff` |

## The decision I need from you

The fix for R13 + R12 is ~6 lines in `_scoped_paths`' domain branch. **`tests.py` is at 594/600**,
so those 6 lines land it at or over the ceiling — which collides head-on with Finding A1, where I
recommended leaving the extraction to the follow-up ticket that already owns this selector's root
cause.

| Option | Trade |
|---|---|
| **A. Fix both now, extract to make room** | CB-1 ships complete. Costs an extraction that Finding A1 said to defer, widening a boundary meant to be readable in one sitting |
| **B. Fix R13 only, defer R12** | Closes the critical hole. R13 alone may fit under 600 without extraction — needs measuring, not guessing |
| **C. Defer both to the follow-up ticket** | CB-1 stays tight, but ships a fix that is knowingly incomplete for four e2e files. My least favourite: R13 is the same bug, and "we knew" is worse than "we missed it" |

**My recommendation: B**, then C for R12 in the follow-up ticket. R13 is the bug this boundary
claims to have fixed; R12 is a cosmetic asymmetry that cannot cause a wrong result.

> Comment:
