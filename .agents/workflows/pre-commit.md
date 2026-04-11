---
description: Run a pre-commit quality gate for the current feature before marking it done.
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

> [!CAUTION]
> **STRICT COMPLIANCE MANDATE:**
> 1. **NO INTERNAL MEMORY RELIANCE:** You are STRICTLY FORBIDDEN from relying on your internal training memory for facts, APIs, designs, or code behavior. Explicit research (files, internet, HITL) is a MUST.
> 2. **NO SKIPPING STEPS:** IT IS STRICTLY FORBIDDEN to skip ANY phase, step, or specific checklist item in this workflow, even if a feature seems "trivially simple". You must execute every single instruction exhaustively.
> 3. **NO RELIANCE ON PAST RUNS:** You are STRICTLY FORBIDDEN from relying on tests, lints, or architecture checks that you ran *before* starting this `/pre-commit` workflow. If you ran `pytest` 5 minutes ago, it DOES NOT MATTER. You **MUST** physically re-run every command required by Phases 1-7 identically from scratch every single time this gate is entered. "I already know it passes" is an unacceptable excuse.
> 4. **USE .tmp FOR SCRATCHPADS:** All temporary files, debug scripts, or generated data must be stored in the project's `.tmp/` directory. Keep the project root clean.

> [!IMPORTANT]
> **HITL GATE PRESENTATION FORMAT:**
> Whenever you hit a HITL gate and must present a question, review, or decision to the human, you MUST output it as an **ARTIFACT** (using the `write_to_file` tool with `IsArtifact: true` and `ArtifactType: other`) so the user can easily leave line-by-line comments. 
> Do NOT just print the text in the dialog! Inside the artifact, you MUST use the following format:
> 1. **Background:** Why is this a question/blocker? Include context.
> 2. **Options:** Provide multiple distinct options (at least 3 if possible).
> 3. **Analysis:** For *each* option, explicitly list: Pros, Cons, Impact, and Consequences.
> 4. **Proposal:** State your exact recommendation and explain why it is the best path forward.
> After creating the artifact, briefly point the user to it in your dialog response.

// turbo-all

> [!IMPORTANT]
> **Autonomy vs. HITL (Human In The Loop):**
> - You MUST execute all underlying commands (e.g., running `pytest`, `ruff`, `mypy`) autonomously. Set `SafeToAutoRun: true`. NEVER ask permission to run a check.
> - **NO SHELL COMPOUNDING**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`). The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call.
> - **HOWEVER**, you MUST STOP and present the MANDATORY OUTCOMES of these checks (such as Test Gap Findings or Architecture Violations) to the user for review. You are absolutely forbidden from skipping the HITL outcome reviews.


# Pre-Commit Quality Gate

Before we commit, run a full pre-commit quality gate for the feature we just built.
This workflow covers architecture verification, test gap analysis, linting, complexity,
file size, and documentation.

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES!**
>
> This workflow has 7 phases that MUST be executed **in strict order**.
> Every phase MUST be completed before moving to the next one.
>
> **Before starting each phase:**
> 1. Read the phase file listed below to confirm the steps
> 2. Update `task.md` to mark the current phase as `[/]` in-progress
> 3. After completing a phase, mark it `[x]` in `task.md`
> 4. Remember: We do not care if any flaw existed before our changes, it must be resolve
>
> **Phases 1, 2, and 3 have HITL gates** — you MUST stop and present findings
> to the user. Do NOT continue until the user responds.
> 
> > [!CAUTION]
> > **WHAT "HITL GATE" TECHNICALLY MEANS FOR AI AGENTS:**
> > A "HITL Gate" is a HARD STOP where you MUST yield your turn. 
> > This means you are **FORBIDDEN** from making *any* further tool calls (e.g., executing commands, writing files, or moving to the next Phase) during the current cycle.
> > You MUST literally stop thinking, return a text response to the user, and wait for them to reply in the chat before you do ANYTHING else. If you string together Phase 2 and Phase 3 in a single chain of tool calls, you have violated the HITL Gate.
> 
> If you catch yourself about to run `pytest` or "verify everything works"
> before completing Phase 2 and Phase 3 — **STOP immediately**.
> That is Phase 4. You are skipping phases.
> 
> **CRITICAL:** AI Agents have a known tendency to skip Phase 3 (Implement Missing Tests).
> This is UNACCEPTABLE. You MUST explicitly write tests for every gap and branch you find.

## Phases

Execute each phase by reading and following the instructions in its workflow file.

| Phase | File | Description | HITL Gate? |
|-------|------|-------------|------------|
| **1** | `.agents/workflows/pre-commit/phase-1-architecture.md` | Architecture verification | ⚠️ Yes (step 1.9) |
| **2** | `.agents/workflows/pre-commit/phase-2-test-gap.md` | Test gap analysis (coverage matrix + test stories) | ⚠️ Yes (step 2.8) |
| **3** | `.agents/workflows/pre-commit/phase-3-implement-tests.md` | Implement missing tests | ⚠️ Yes (step 3.1b) |
| **4** | `.agents/workflows/pre-commit/phase-4-test-suite.md` | Run full test suite | No |
| **5** | `.agents/workflows/pre-commit/phase-5-code-quality.md` | Code quality checks (ruff, mypy, complexity, file size) | No |
| **6** | `.agents/workflows/pre-commit/phase-6-documentation.md` | Documentation updates | No |
| **7** | `.agents/workflows/pre-commit/phase-7-walkthrough.md` | Write walkthrough artifact | No |

> [!IMPORTANT]
> Every bug, lint error, complexity violation, or oversized file MUST be fixed
> regardless of whether it is pre-existing or introduced by this feature.
> No inherited problems are acceptable!

## Phase 8: Commit Boundary (HITL)

> [!CAUTION]
> **HARD STOP REQUIRED:** You MUST NOT proceed past a commit boundary autonomously.

8.1. After Phase 7 completes, the `/pre-commit` gate is finished.
8.2. **STOP execution**. Inform the user that the pre-commit gate is complete.
8.3. **WAIT** for the user to perform the commit or explicitly tell you to proceed. Do absolutely nothing else.
