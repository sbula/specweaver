---
description: "Phase 3: Feature Detail — define FRs/NFRs, validate external APIs, and verify architectural alignment. HITL gates fire on gaps, incompatibilities, or any Architectural Switch."
---

# Phase 3: Feature Detail

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Derive and validate autonomously. Three categories of HITL gate:
> - Vague or missing requirements (after exhausting research)
> - API incompatibility or version conflict
> - Any Architectural Switch (hard stop, no exceptions)

---

## Section A — Functional Requirements

A.1. Using the working definition (Phase 1) and research brief (Phase 2),
     derive every Functional Requirement for this feature.

     Each FR MUST be:
     - **Numbered**: `FR-1`, `FR-2`, ...
     - **Unambiguous**: exactly one valid interpretation
     - **Testable**: a test can pass or fail based on this FR
     - **Structured**: Actor + Action + Outcome
       Example: "The system SHALL record model_id, prompt_tokens, and completion_tokens
       for every LLM call and persist them to the telemetry DB."

A.1a. **Seams are FRs on THIS capability — `ADR-003`.** If this feature calls, reads from, or
     persists through another module, that is a requirement of *yours*, not an observation about
     two other modules and not work for a later integration story. There is no later integration
     story; the family was retired precisely because it became a second place to claim things no
     gate compared against code (`INT-US-21-SUB` advertised recursive decomposition that was never
     built, through delivery and an epic closure).

     Write it as an FR like any other, naming the provider and the surface:

     > *"FR-6: `MemoryHydrator` SHALL deserialise `Task.handover_context` (written by `B-INTL-09`)
     > via `HandoverContext.from_json_str()`, logging at WARNING and returning empty on invalid
     > payloads."*

     Its proof tier is **integration** (see the dev and implementation-plan skills), and
     `check_fr_coverage.py` then enforces it exactly as it does every other FR — a plan that owns
     it, a test that cites it.

A.1b. **Iterate FR ↔ surface until it converges. This is a fixpoint, NOT an ordering.**

     An FR states an outcome, which determines the data you need, which names the surface you
     consume. But the surface that *actually exists* constrains what the FR can promise — which
     rewrites the FR. Ordering it either way fails: surfaces first has you inventing APIs for
     requirements you have not derived; surfaces strictly after has you writing requirements
     against APIs you have not checked.

     ```
     FR states an outcome -> data it must read/send -> whose module provides it
                          -> what that surface really offers -> back to a now-DIFFERENT FR
     ```

     Loop that until it settles, then **record where it settled**. One row per FR that crosses a
     module boundary — not every FR, or a diagnostic becomes paperwork:

     | FR | Data needed | Provider · surface | Verified how |
     |---|---|---|---|
     | FR-5 | open defects for a BLOCKED task | `B-INTL-09` · `list_defects(task_id, status=OPEN)` | read `repository/core.py` |

     > [!IMPORTANT]
     > **Termination condition: every row names a surface someone has READ, not assumed.**
     > This is the standard `check_story_preconditions.py` already applies to prerequisites, and for
     > the same reason — `INT-US-21` recorded three prerequisites as `✅` and all three were
     > materially broken. Document state lies; reading does not. "Verified how" must cite the file
     > or symbol you opened, never "per the design" or "assumed available".

     **NFRs fall out of this table for free.** A surface's latency budget, payload cap or failure
     mode becomes your NFR — which is where `D-INTL-06`'s 2048-token and 8KB bounds actually came
     from. Carry them into Section B rather than inventing thresholds there.

A.1c. **Three outcomes when a row does not converge. All are findings, none is a failure.**

     | Outcome | What it means | What you do |
     |---|---|---|
     | **Surface provides it** | the FR stands | note its proof tier is **integration**, not unit |
     | **Wrong side owns it** | the responsibility sits with the provider | **rewrite the FR** |
     | **Surface does not exist** | the provider needs a new FR | a cross-story dependency — **HITL, A.1d** |

     The middle one is not hypothetical. `D-INTL-06` FR-3 reads *"Selective Filtering |
     MemoryHydrator | Filter out ARCHIVED tasks, tasks outside the project, DONE tasks > 24h old"* —
     and the hydrator does not filter at all. It passes `max_age_hours=24` to the repository
     (`hydrator.py:162`). The FR and the interface disagreed and the FR was never updated; it
     surfaced two capability-releases later as *"FR-3's proof would have to live in the provider's
     test file"*. One iteration of **which side actually owns this?** catches it at design time.

A.1d. **HITL gate** (fires when a surface this feature needs does not exist):
     Name the FR, the data it needs, and the provider that would have to supply it. State plainly
     that the provider needs a new FR and that this feature is blocked on it or must descope.
     **STOP. Wait.** Do not design around it silently, and do not defer it to "integration" — that
     is exactly the deferral `ADR-003` removed, and it is how a capability ships with a promise
     nothing implements.

A.2. Review each FR for vagueness:
     - Does it use words like "fast", "good", "some", "various", "appropriate"? → vague.
     - Does it have multiple interpretations? → vague.
     - Could you write a test for it? If no → too vague.

A.3. **HITL gate** (fires for each vague FR after exhausting research):
     Present the specific FR and the gap.
     Ask ONE targeted clarifying question.
     **STOP. Wait. Do NOT proceed with a vague requirement.**

---

## Section B — Non-Functional Requirements

B.1. List all NFRs. Each must have a concrete threshold where applicable:
     - **Performance**: latency budgets, throughput targets, memory limits
     - **Security**: authentication, authorization, input validation, data exposure
     - **Compatibility**: Python version, OS, existing DB schema, existing CLI contracts
     - **Observability**: logging requirements, error reporting, telemetry
     - **Error handling**: behavior on failure, retry policy, fallback behavior
     - **Data migration**: backward compat, migration strategy, rollback plan

B.1a. **State how each NFR will be PROVED — `check_nfr_sweep.py` ratchets the ones a test could
      prove, and only those.** Most NFRs are behavioural and need a test like any FR. Where a
      pytest is genuinely the wrong instrument, mark the row so the excuse is visible in review
      rather than hidden in a checker's skip-list:

     | Marker | Use when | Example |
     |---|---|---|
     | `**[proof: arch — tach/lint gate, not pytest]**` | a boundary, placement or size rule another gate already enforces | *"`llm/` must remain an adapter and forbid `loom/*`"* → `tach check` |
     | `**[proof: meta — rule about tests, docs or the diff]**` | a rule about the tests, the docs, or the change itself | *"unit tests SHALL mock at the `execute()` boundary"* |
     | `**[proof: none — unfalsifiable as written]**` | no test could pass or fail it as phrased | *"token reductions without decreasing accuracy"* — no threshold |

     > [!CAUTION]
     > **`[proof: none]` is a confession, not a hiding place.** It says the requirement was written
     > so that nothing can check it. Prefer fixing the wording — give it a threshold — and reach for
     > the marker only when the row is a scope statement or a rationale rather than a requirement.
     > Marking rows to make the ratchet fall is the same gaming as a bulk citation, with an audit
     > trail pointing at you.

     Measured 2026-08-13, before this rule existed: 224 NFRs on delivered stories, **37 cited**.
     62 rows were genuinely non-behavioural; the other 128 were simply untested.

B.2. **HITL gate** (fires if a critical NFR threshold is unknown):
     "Critical" means: security risk, data loss risk, or backward compatibility break.
     Ask for the specific threshold.
     **STOP. Wait.**

---

## Section C — External API & Tool Validation

C.1. For each external tool identified in Phase 2:
     a. Check `pyproject.toml` for the currently declared version.
     b. Verify the specific API surface this feature needs is stable:
        not `@experimental`, not `@deprecated`, not removed at the target version.
     c. Record: `Tool | Min Version | API Surface | Stable (Y/N) | Notes`

C.2. **HITL gate (hard stop)** — if any incompatibility is found:
     - Identify the tool, the needed API, and the conflict precisely.
     - Present at least 2 concrete options (upgrade, alternative tool, different approach).
     - **STOP. Wait for the user's decision.**
     - Do NOT proceed past a broken dependency.

---

## Section D — Architectural Alignment

D.1. For each change the feature requires (new file, modified module, new dependency,
     new DB table, new pipeline step, new CLI command):
     - Map it to the architecture reference module map.
     - Verify it fits in an existing module, or justify why a new module is needed.
     - Verify it respects `consumes`/`forbids` rules in the target module's `context.yaml`.
     - Verify it follows the archetype constraints of the target module
       (`pure-logic` = no I/O, `adapter` = wraps externals, `orchestrator` = delegates).

D.2. For each proposed change, verify no existing capability is being duplicated.
     Could an existing module be extended instead of creating new infrastructure?

D.3. **HITL gate (hard stop)** — ANY proposed change that would:
     - Place code in the wrong architectural layer
     - Violate a `forbids` rule in `context.yaml`
     - Introduce a circular import
     - Duplicate existing infrastructure
     - Add a volatile dependency to a stable module (`config/`, `context/`, `validation/`)

     ...is an **Architectural Switch** and MUST be presented as follows:
     1. State exactly which rule or pattern would be violated.
     2. State why the switch may be necessary.
     3. Offer at least 1 alternative that avoids the switch.
     4. Give a recommendation with explicit rationale.

     **STOP. Wait for explicit user approval.**
     If approved: note in the design doc — "Approved by <user> on <date>."

> [!CAUTION]
> **HARD STOP on every Architectural Switch. No exceptions.**
> Even if the switch seems obviously correct, it must receive explicit human sign-off.
> The architecture is the shared contract. Unilateral deviations compound into chaos.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 3 complete. FRs, NFRs, API validation, and arch decisions documented.
> Proceed to Phase 4 (Decomposition).
