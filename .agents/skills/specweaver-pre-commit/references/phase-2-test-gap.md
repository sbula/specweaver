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
> Before trusting ANY existing test as coverage, verify it can actually **fail** for the reason it
> claims. A test that cannot distinguish the states it asserts about is worse than no test: it
> reports green and suppresses the gap from this very analysis.
>
> **You MUST NOT cite an existing test as covering a gap until you have read its body.**
> "There is a test named `test_x_flows_through`" is not a finding. What it asserts is.

Check every test you intend to rely on against these six patterns. All six are real defects found
in this repo (INT-US-21 SF-01, 2026-07-25) — none were hypothetical, and each hid a live bug:

| # | Pattern | How to detect it |
|---|---|---|
| 1 | **Ambiguous exit code** — asserts `exit_code == 0` where *two or more* outcomes exit 0 | Ask: which distinct end states share this code? A PARKED and a COMPLETED run both exit 0. Assert the **persisted status**, not the process code |
| 2 | **Stubbed-away subject** — the test replaces the very component under test | e.g. registering a fake handler for *every* step, then claiming the test proves the real registry resolves them. Grep the test for wholesale registry/handler substitution |
| 3 | **Never executed** — a skip guard that is always true | `if not path.exists(): pytest.skip(...)` with a wrong path silently skips forever. Compare skip counts before/after your change; an unexplained skip is a dead test |
| 4 | **Fixture cannot satisfy the assertion** — the input could never produce the asserted outcome | Run the real validator/battery against the fixture once. A spec fixture that scores 4/6 can never prove "the chain validates it" |
| 5 | **Escaped mock** — a "mocked" test reaching a real network/paid API | Look for *alternative* resolution paths that bypass the patch (e.g. a router/factory that builds its own client). Check logs for real endpoints, timeouts, 4xx/5xx quota errors |
| 6 | **Assertion weaker than the claim** — the docstring promises more than the assert checks | Read the test name and docstring, then the asserts. "flows through the whole chain" backed by a single truthiness check is a gap, not coverage |

For each one you find, it is a **finding for this analysis**, not a footnote: list it in the
coverage matrix as `❌`/`🟡` (never `✅`) and raise a story to make it honest. Per the
fix-inherited-failures rule, a vacuous test in code you touched must be repaired, not deferred.

> [!TIP]
> The cheapest reliable probe: **make the test fail on purpose.** Break the behaviour it claims to
> cover and confirm it goes red. If it stays green, you have found pattern 1, 2, or 6.

2.6. Do NOT invent arbitrary test counts. Every story must trace to real code.
2.7. Present the FULL list — do NOT limit to 10 items.
2.8. **STOP and wait for the HITL response.** Present the gap analysis.
     > [!CAUTION]
     > You MUST write the test gap analysis into a system Artifact (using `write_to_file` with `IsArtifact: true`)!
     > You MUST NOT print the Coverage Matrix or Test Stories directly into your conversational chat response. The user needs the Artifact to leave line-by-line comments.

> [!CAUTION]
> **MANDATORY HITL YIELD:** You MUST stop execution and present the Coverage Matrix and Proposed Test Stories as an Artifact. 
> You MUST YIELD YOUR TURN. A yield means making ZERO further tool calls after generating the Artifact. You must end your response and wait for the user to type a reply.
> You MUST NOT proceed to Phase 3 (implementing tests) synchronously in the same turn. Do not assume they look okay or skip this gate.
