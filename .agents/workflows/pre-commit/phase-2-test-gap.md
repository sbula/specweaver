---
description: "Phase 2: Test gap analysis — coverage matrix, proposed test stories, and HITL gate."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

// turbo-all

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute the gap analysis steps autonomously, but you MUST STOP and present the results. NEVER bypass the user review of the findings.


# Phase 2: Test Gap Analysis

2.1. Read EVERY source file that was created or modified for this feature.
2.2. For each file, go line-by-line and identify EVERY branch, guard clause,
     error path, boundary condition, edge case, and fallback. Reference
     the source line numbers.
2.2. Read EVERY existing test file that covers these modules (unit, integration,
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

2.6. Do NOT invent arbitrary test counts. Every story must trace to real code.
2.7. Present the FULL list — do NOT limit to 10 items.
2.8. **STOP and wait for the HITL response.** Present the gap analysis.
     > [!CAUTION]
     > You MUST NOT write the test gap analysis into a file or system Artifact!
     > You MUST print the full Background, Coverage Matrix, Options, Analysis, and Proposal DIRECTLY into your conversational chat response. 
     > Write it exactly like a review straight to the user in the text window.

> [!CAUTION]
> **MANDATORY HITL YIELD:** You MUST stop execution and present the Coverage Matrix and Proposed Test Stories directly in the chat to the user. 
> You MUST YIELD YOUR TURN. A yield means making ZERO further tool calls. You must end your response and wait for the user to type a reply in the chat.
> You MUST NOT proceed to Phase 3 (implementing tests) synchronously in the same turn. Do not assume they look okay or skip this gate.
