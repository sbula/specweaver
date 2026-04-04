---
description: "Phase 3: Test gap analysis — coverage matrix, proposed test stories, and HITL gate."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

// turbo-all

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute the gap analysis steps autonomously, but you MUST STOP and present the results. NEVER bypass the user review of the findings.


# Phase 3: Test Gap Analysis

3.1. Read EVERY source file that was created or modified for this feature.
3.2. For each file, go line-by-line and identify EVERY branch, guard clause,
     error path, boundary condition, edge case, and fallback. Reference
     the source line numbers.
3.3. Read EVERY existing test file that covers these modules (unit, integration,
     e2e). Do NOT guess — actually read the test files and list what scenarios
     they already cover.

3.4. **Deliverable 1 — Coverage Matrix** (one table per source module/file):

     > [!CAUTION]
     > **MANDATORY FORMAT EXCEPTION:** EVEN IF the feature contains zero Python logic and only modifies configuration files (e.g. `.toml`, `.md`, or deleting files), you MUST STILL present the exact matrix table format below for the impacted files. Do not skip the matrix. Use the ✅/🟡/❌ format religiously.

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

3.5. **Deliverable 2 — Proposed Test Stories** (flat list, grouped by kind):

     Each proposed new test is written as a **story** with the kind clearly
     tagged. Stories are grouped under headings: `### Unit`, `### Integration`,
     `### E2E`.

     Example:

     ### Unit
     | # | Story | Target Class/Function | Source Line |
     |---|-------|-----------------------|-------------|
     | 1 | Resolver skips candidates outside workspace boundary | `_resolve_mentions()` | L247 |
     | 2 | Scanner stores nothing when no mentions found | `_scan_and_store_mentions()` | L193 |

     ### Integration
     | # | Story | Target Seam | Source Lines |
     |---|-------|-------------|-------------|
     | 3 | Scanner → resolver → feedback with real files | `extract_mentions` → `_resolve_mentions` → `context.feedback` | L181-213 |

     ### E2E
     (none proposed / or list here)

3.6. Do NOT invent arbitrary test counts. Every story must trace to real code.
3.7. Present the FULL list — do NOT limit to 10 items.
3.8. **STOP and wait for the HITL response.** Present the gap analysis to the
     user and wait for their feedback before proceeding. Do NOT continue
     until the user confirms or provides changes.
     Include in the HITL notification:
     - The coverage matrix (Deliverable 1)
     - The proposed test stories (Deliverable 2)
     - Your reasoning for each gap's priority
     - Any recommendations for deferral vs. immediate fix
     - Any issues discovered during the analysis

> [!CAUTION]
> **MANDATORY HITL YIELD:** You MUST stop execution and present the Coverage Matrix and Proposed Test Stories to the user. 
> You MUST YIELD YOUR TURN. A yield means making ZERO further tool calls. You must end your response and wait for the user to type a reply in the chat.
> You MUST NOT proceed to Phase 4 (implementing tests) synchronously in the same turn. Do not assume they look okay or skip this gate.
