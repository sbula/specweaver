---
name: specweaver-pre-commit
description: "Pre-commit quality gate. Architecture verification, test gap analysis, implement
missing tests, run full test suite, code quality checks, documentation updates, walkthrough. Use
when the user asks to run pre-commit checks, quality gates, or verify code before committing."
---

# Pre-Commit Quality Gate Skill

```
Trigger: "pre-commit", "quality gate", "run pre-commit checks",
         "verify before commit", "pre-commit gate"
```

Before we commit, run a full pre-commit quality gate for the feature we just built.
This skill covers architecture verification, test gap analysis, linting, complexity,
file size, and documentation.

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES!**
>
> This skill has 7 phases that MUST be executed **in strict order**.
> Every phase MUST be completed before moving to the next one.
>
> **Before starting each phase:**
> 1. Read the phase file from the `references/` directory listed below
> 2. Update `task.md` to mark the current phase as `[/]` in-progress
> 3. After completing a phase, mark it `[x]` in `task.md`
> 4. Remember: We do not care if any flaw existed before our changes, it must be resolved
>
> **Phases 1, 2, and 3 have HITL gates** — you MUST stop and present findings
> to the user. Do NOT continue until the user responds.
> 
> > [!CAUTION]
> > **WHAT "HITL GATE" TECHNICALLY MEANS:**
> > A "HITL Gate" is a HARD STOP where you MUST yield your turn. 
> > This means you are **FORBIDDEN** from making *any* further tool calls (e.g., executing commands, writing files, or moving to the next Phase) during the current cycle.
> > You MUST literally stop thinking, return a text response to the user, and wait for them to reply
> > in the chat before you do ANYTHING else. If you string together Phase 2 and Phase 3 in a single
> > chain of tool calls, you have violated the HITL Gate.
> 
> If you catch yourself about to run `pytest` or "verify everything works"
> before completing Phase 2 and Phase 3 — **STOP immediately**.
> That is Phase 4. You are skipping phases.
> 
> **CRITICAL:** AI Agents have a known tendency to skip Phase 3 (Implement Missing Tests).
> This is UNACCEPTABLE. You MUST explicitly write tests for every gap and branch you find.

> [!IMPORTANT]
> **NO RELIANCE ON PAST RUNS:** You are STRICTLY FORBIDDEN from relying on tests, lints, or
> architecture checks that you ran *before* starting this pre-commit skill. If you ran `pytest` 5
> minutes ago, it DOES NOT MATTER. You **MUST** physically re-run every command required by Phases
> 1-7 identically from scratch every single time this gate is entered. "I already know it passes" is
> an unacceptable excuse.

## MCP Tool Guidance

When available, prefer these MCP tools over grep/file-reading:

- **Architecture verification (Phase 1):** Use `codebase-memory` → `trace_path` to verify imports respect layer boundaries after changes.
- **Test gap analysis (Phase 2):** Use `codebase-memory` → `search_graph` to find all callers of modified functions — each caller needs test coverage.
- **Fall back to grep/file-reading** if MCP tools are unavailable.

## Phases


Execute each phase by reading and following the instructions in its reference file.

| Phase | File | Description | HITL Gate? |
|-------|------|-------------|------------|
| **1** | `.agents/skills/specweaver-pre-commit/references/phase-1-architecture.md` | Architecture verification | ⚠️ Yes (step 1.9) |
| **2** | `.agents/skills/specweaver-pre-commit/references/phase-2-test-gap.md` | Test gap analysis (coverage matrix + test stories) | ⚠️ Yes (step 2.8) |
| **3** | `.agents/skills/specweaver-pre-commit/references/phase-3-implement-tests.md` | Implement missing tests | ⚠️ Yes (step 3.1b) |
| **4** | `.agents/skills/specweaver-pre-commit/references/phase-4-test-suite.md` | Run full test suite | No |
| **5** | `.agents/skills/specweaver-pre-commit/references/phase-5-code-quality.md` | Code quality checks (ruff, mypy, complexity, file size) | No |
| **6** | `.agents/skills/specweaver-pre-commit/references/phase-6-documentation.md` | Documentation updates | No |
| **7** | `.agents/skills/specweaver-pre-commit/references/phase-7-walkthrough.md` | Write walkthrough artifact | No |
| **7.5** | N/A | **Red/Blue Adversarial Review of Code Changes** | ⚠️ Yes (step 7.5.2) |

> [!IMPORTANT]
> Every bug, lint error, complexity violation, or oversized file MUST be fixed
> regardless of whether it is pre-existing or introduced by this feature.
> No inherited problems are acceptable!

> [!NOTE]
> **The mutation corpus is NOT part of this gate, deliberately.** `scripts/mutation.py` runs
> nightly and is judged by `mutation.py --gate` in the morning — a separate decision about whether
> feature work continues, never a commit gate (`TECH-049` `NFR-6`). Blocking a commit on it would
> mean an on-demand corpus run, and a gate that slow gets switched off.
>
> What belongs *here* is the campaign itself: when a boundary calls a claim **proven**, write it
> into `<ID>_mutants.json` beside the design so the nightly run keeps re-asking.
> See `docs/dev_guides/writing_mutation_campaigns.md`.

## Phase 7.5: Red/Blue Cycle Check

7.5.1 Execute the `specweaver-red-blue-review` skill against the code changes introduced in this
commit boundary. Look for security flaws, unhandled edge cases, architecture violations, and
incomplete requirements.
7.5.2 If the cycle produces findings, **STOP** and present them to the user for review. You must resolve critical findings before proceeding to Phase 8.

## Phase 7.9: Is anything lost if this session ends here?

The commit captures the code. It does not capture the three things a handover exists for, and none of
them are recoverable from `git log`:

1. **A decision now waiting on the user.** Any HITL gate you stopped at, with the document that must be
   read before answering it.
2. **An approach measured and rejected.** If you tried something and the measurement said no, record
   it where the next person will look *before* trying it again — the design or the analysis, not just
   the commit message. A rejected approach that is not written down is a rediscovery cost.
3. **A pointer that must be read first.** Any `docs/analysis/` document you produced, and what must not
   be touched before reading it.

Put each in its **durable** home first — the design, the analysis, the contract row. Only then add a
one-line pointer to `.tmp/HANDOVER.md`. A handover that restates what the artefacts already hold is the
one nobody reads; a handover that is an index of them is the one that works.

**Do not turn it into a changelog.** `git log --oneline` covers what changed. The handover covers what
is *unfinished, undecided, or not to be repeated*.

### Two files, and they are not the same thing

| File | Holds | Lives |
|---|---|---|
| `.agents/STATE.md` | Where the **project** stands — delivered, set back, missing | Committed |
| `.tmp/HANDOVER.md` | Where **this session** stands — open gates, loose ends | Gitignored |

**Update `STATE.md` when this boundary changed the project's position**: a capability flag moved, a
correction became owed, something that was missing is now there. It is short on purpose; if the
answer is "nothing changed for the project", change nothing.

Nothing checks `STATE.md` for staleness. A confident file describing a repo that has moved is the
same defect as a stale suite count, and it fails silently — which is why updating it is a step here
rather than a habit.

The *state* half is generated, so do not hand-write it:

```bash
python scripts/session_handover.py            # git, registries, sweeps — seconds
python scripts/session_handover.py --gates    # also runs quality.py cb + doc
python scripts/session_handover.py --suite    # also runs the full suite for the real count
```

It rewrites only the marked block and returns every other line byte for byte. Numbers copied by hand
are the ones that go stale, so copy none of them.

## Phase 8: Commit Boundary (HITL)

> **HARD STOP REQUIRED:** You MUST NOT proceed past a commit boundary autonomously.

8.1. After Phase 7.5 completes, the pre-commit gate is finished.
8.2. **STOP execution**. Inform the user that the pre-commit gate is complete.
8.3. **WAIT** for the user to perform the commit or explicitly tell you to proceed. Do absolutely nothing else.
