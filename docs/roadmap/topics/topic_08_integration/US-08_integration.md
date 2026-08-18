# US-08 Integration - Integration Contracts

## Base Story Contract (`INT-US-08`)
* **Status:** ⬜ Pending
* **Integration Description:** [Pending definition...]
* **Verifiable Proof:** [Pending]

## Sub-Story Add-Ons

* **`INT-US-08` base — Greenfield Bootstrap Wizard:** the story's contract under `ADR-004`.

  ### Path Inventory

  | # | Path | Span | Owner | Runnable today | Blocker |
  |---|---|---|---|---|---|
  | P-1 | A project's declared `context.yaml` files become a queryable graph of modules and edges | single feature | `D-SENS-01` | yes — **done** | — |
  | P-2 | A directory that declares nothing is analysed and given a node, so the graph covers the project rather than its documented part | cross-module | `D-SENS-01` | yes — **done** | — |
  | P-3 | Seam: a module's neighbourhood is rendered into a prompt inside a character budget | cross-module | `D-SENS-01` | yes — **done** | — |
  | P-4 | Cycles and contradictory SLAs are surfaced as findings | single feature | `D-SENS-01` | yes — **done** | — |
  | P-5 | Journey: the wizard bootstraps an undocumented project and the graph it produces is what the first prompt carries | cross-feature | `D-SENS-01` | yes — **done** | — |

  **`D-SENS-01` had no design document and no feature directory.** It is a `✅` foundation — the topic
  entry calls it exactly that — recorded in four lines of a topic file and nowhere else. That makes it
  invisible to `check_fr_sweep.py` by construction: the sweep counts uncited FRs in designs that exist,
  and a design that does not exist has none. Seven FRs are now written from why the capability exists,
  each behind a killed mutant, and the design and an ownership record now exist under
  `features/topic_02_sensors/D-SENS-01/`.

  **FR-1's mutant fails 50 test files across all three tiers** — replacing the `context.yaml` walk with
  an empty iterable. Selectors, staleness, the graph CLI and the tach-sync journey all rest on that one
  loop. When a topic entry claims something is a foundation, this is what confirming it looks like.

  **FR-2's mutant is the one worth carrying forward.** `impact_of` traverses reverse; flipping it to
  forward returns the module's *dependencies* where its *consumers* belong. Both are non-empty sets of
  real module names, both read plausibly in a prompt, and the direction is the whole point of the query.
  An impact analysis pointing the wrong way is worse than none, because it reads as reassurance.

  **One mutant, two capabilities — declared, not glossed.** That same flip is already `A-SENS-01` FR-3's
  citation, from `INT-US-11-SF01-MIG`: recursive upward invalidation and blast-radius direction are two
  claims at different altitudes over one line of code. So the second citation is not independent
  evidence, and both the design and the test file say so. A ledger of killed mutants that counts this
  once is right; one that counts it twice is flattering itself.

  Not claimed here: staleness. The merkle-boundary comparison lives in `TopologyGraph` but belongs to
  `A-SENS-01`'s cache. Citing it to the graph as well would double-count one behaviour across two
  capabilities — the thing the paragraph above exists to avoid.

  P-5 waits on a test, not a feature.

  **`INT-US-08-MIG` is discharged (2026-08-17); the contract stays open** on P-5.

  **P-5 closed 2026-08-18** —
  `tests/e2e/capabilities/infrastructure/test_inferred_topology_reaches_the_prompt_e2e.py`. An
  undocumented project, inference, and then the assertion that matters: the *purpose inference read out
  of the source* appears in the built prompt. Not that a `<topology>` block exists — an empty one would
  satisfy that and tell the model nothing.

  **An e2e for this appeared to exist and did not.** `test_topology_e2e.py` advertises *"sw review
  --selector nhop injects neighbor context into prompt"*, runs `sw scan`, runs the review, and then
  asserts `exit_code in (0, 1)` and no traceback — a check that the command did not crash, which also
  accepts failure. Its docstring made a claim its assertions never made.

  One trap recorded in the test: `TopologyContext.get_prompt_content` renders the same fields in the
  same layout and is **not** the renderer on this path — `PromptBuilder.add_topology` builds the line
  itself. Mutating the former leaves the test green.
