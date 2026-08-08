---
description: "Phase 2: Test gap analysis — FR/NFR/RT/AD coverage check, coverage matrix, proposed test stories, and HITL gate."
---

# Phase 2: Test Gap Analysis

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute the gap analysis steps autonomously, but you MUST STOP and present the results. NEVER bypass the user review of the findings.

2.0. **MANDATORY PRE-CHECK**: Before analyzing test gaps, re-read the Design Document.
     Verify ALL of the following are covered by existing tests:
     - Every Functional Requirement (FR) assigned to this sub-feature
     - Every Non-Functional Requirement (NFR) that applies
     - Every Architectural Decision (AD) — are the constraints enforced by tests?
     - Every Risk/Trade-off (RT) — are mitigations verified by tests?
     If ANY are not covered, they MUST appear as gaps in the coverage matrix below.

> [!CAUTION]
> **Unit, integration, and e2e tests serve DIFFERENT purposes. They are NOT interchangeable.**
> - **Unit tests**: Test individual functions/classes in isolation. Mock all dependencies.
> - **Integration tests**: Test seams between 2+ real components. Use real implementations.
> - **E2E tests**: Test complete user-facing workflows end-to-end.
> Ensure sufficient coverage at ALL THREE levels. Do not substitute one for another.

2.1. Read EVERY source file that was created or modified for this feature.
2.2. For each file, go line-by-line and identify EVERY branch, guard clause,
     error path, boundary condition, edge case, and fallback. Reference
     the source line numbers.
2.3. Read EVERY existing test file that covers these modules (unit, integration,
     e2e). Do NOT guess — actually read the test files and list what scenarios
     they already cover.

2.4. **Deliverable 1 — Coverage Matrix** (one table per source module/file):

     > [!CAUTION]
     > **MANDATORY FORMAT EXCEPTION:** EVEN IF the feature contains zero Python logic and only modifies configuration files (e.g. `.toml`, `.md`, or deleting files), you MUST STILL present the exact matrix table format below for the impacted files. 
     > **STRICT COMPACTNESS:** Do NOT generate scrolling paragraphs, do NOT generate Mermaid diagrams, and do NOT overcomplicate it. Use ONLY the compact markdown table format below.

     Rows = classes/functions in the module.
     Columns = Unit | Integration | E2E.
     Cell values:
     - `❌` = no test exists for this class/function at this level
     - `🟡` = tests exist but coverage is insufficient (gaps remain)
     - `✅` = adequately covered

     Example:

     **Module: `flow/_review.py`**

     | Class / Function | Unit | Integration | E2E |
     |------------------|------|-------------|-----|
     | `_resolve_mentions()` | ❌ | ❌ | ❌ |
     | `_scan_and_store_mentions()` | ❌ | ❌ | ❌ |
     | `_is_within()` | ❌ | — | — |
     | `ReviewSpecHandler` | ✅ | 🟡 | ❌ |

     Use `—` when a test kind does not apply (e.g., e2e for a pure helper).

2.5. **Deliverable 2 — Proposed Test Stories** (flat list, grouped by kind):

     > [!CAUTION]
     > **ADVERSARIAL TEST MATRIX MANDATE:** When proposing new test stories, you MUST explicitly categorize them into the 4 Adversarial Matrix buckets: `[Happy Path]`, `[Boundary/Edge Case]`, `[Graceful Degradation]`, or `[Hostile/Wrong Input]`.
     > Every single module with a gap MUST have at least one story covering each of these 4 buckets unless explicitly justified.

     Each proposed new test is written as a **story** with the kind clearly
     tagged. Stories are grouped under headings: `### Unit`, `### Integration`,
     `### E2E`. Include the Matrix Category in the Story description.

     Example:

     ### Unit
     | # | Story | Target Class/Function | Source Line |
     |---|-------|-----------------------|-------------|
     | 1 | [Happy Path] Resolver skips candidates outside workspace boundary | `_resolve_mentions()` | L247 |
     | 2 | [Boundary] Scanner stores nothing when no mentions found | `_scan_and_store_mentions()` | L193 |
     | 3 | [Degradation] Resolver throws specific timeout error if LLM is offline | `_resolve_mentions()` | L250 |
     | 4 | [Hostile] Scanner safely rejects malicious path traversal string | `_scan_and_store_mentions()` | L195 |

     ### Integration
     | # | Story | Target Seam | Source Lines |
     |---|-------|-------------|-------------|
     | 3 | Scanner → resolver → feedback with real files | `extract_mentions` → `_resolve_mentions` → `context.feedback` | L181-213 |

     ### E2E
     (none proposed / or list here)

2.5a. **MANDATORY CHALLENGE**: Are you SURE there are not more integration and e2e
      tests needed? Explicitly justify why the proposed set is sufficient. Have you
      covered ALL important, crucial, major, and critical edge cases?

2.5b. **VACUOUS PROOF CHECK (MANDATORY)** — a passing test is not evidence.

> [!CAUTION]
> Read **`references/test-quality.md`** and check every test you intend to rely on against its
> seven patterns. You MUST NOT cite an existing test as covering a gap until you have read its
> body. "There is a test named `test_x_flows_through`" is not a finding. What it asserts is.
>
> Anything you find is a **finding for this analysis**, not a footnote: list it in the coverage
> matrix as `❌`/`🟡` (never `✅`) and add it to Deliverable 2 as a proposed story. Per the
> fix-inherited-failures rule, a vacuous test in code you touched must be repaired, not deferred.
>
> **Do NOT invoke `specweaver-ticket` from inside this phase.** A proposed story is a line item for
> the human to review at the Phase 2 HITL gate (2.8) — it becomes a real TECH ticket only if the
> user asks for one there. Minting on your own initiative mid-phase is the exact failure this note
> exists to prevent (see `specweaver-ticket`'s own incident log).

Run the executable half now — these block, so there is nothing to remember:

```bash
python scripts/quality.py cb --only useless_asserts,test_basenames
```

> Both guards also run as part of the full gate in Phase 5. They are pulled forward here because
> a vacuous assertion found during gap analysis is a finding for THIS phase's coverage matrix,
> and discovering it two phases later means redoing the analysis. `--only` runs exactly those two
> at `cb` scope — the whole `tests/` tree, not just what changed.

> [!TIP]
> The cheapest reliable probe: **make the test fail on purpose.** `test-quality.md` treats this as
> mandatory rather than optional, with four worked examples of what it caught.

2.6. Do NOT invent arbitrary test counts. Every story must trace to real code.
2.7. Present the FULL list — do NOT limit to 10 items.
2.8. **STOP and wait for the HITL response.** Present the combined analysis — the Architecture
     Findings deferred from Phase 1 (§1.9) together with this phase's gap analysis. This is the
     single authority on that format; §1.9 defers to it.
     > [!CAUTION]
     > You MUST write the combined analysis into a **reviewable document the user can comment on
     > line by line** — whatever this harness offers for that. You MUST NOT print the Coverage
     > Matrix or Test Stories directly into your conversational chat response.
     >
     > The requirement is line-by-line commentability, not a particular tool. Name no tool here:
     > an instruction naming a mechanism that does not exist in the harness running it is the
     > same rot as a path that does not resolve.

> [!CAUTION]
> **MANDATORY HITL YIELD:** You MUST stop execution and present the Coverage Matrix and Proposed Test Stories in that document.
> You MUST YIELD YOUR TURN. A yield means making ZERO further tool calls after producing it. You must end your response and wait for the user to type a reply.
> You MUST NOT proceed to Phase 3 (implementing tests) synchronously in the same turn. Do not assume they look okay or skip this gate.
