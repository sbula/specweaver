# Implementation Plan: Native CLI Action Nodes [SF-3: Scaffold, Boundary Config, and Docs]

- **Feature ID**: C-EXEC-02
- **Sub-Feature**: SF-3 — Scaffold, Boundary Config, and Docs
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_sf3_implementation_plan.md
- **Status**: APPROVED

## Scope

Create `.specweaver/scripts/` during project scaffolding (FR-10); wire the two config files SF-1's `BashActionAtom` needs to become a tach-legal import for SF-2 (`tach.toml`'s sandbox interface expose-list, `core/flow/context.yaml`'s `consumes`); correct two stale/imprecise docs (`hard_dependency_rules.md`, `ORIGINS.md`); extend the dev/user guide sections that are genuinely SF-3's own responsibility.

**FRs covered**: FR-10.
**Inputs**: none — parallelizable, does not require SF-1/SF-2 code, only the module *names* SF-1 already introduced.
**Outputs**: `.specweaver/scripts/` exists on every newly-scaffolded project; `tach.toml`/`context.yaml` are ready for SF-2 to pass `tach check`; docs are accurate.
**Depends on**: none.

## Research Notes

- **`workspace/project/scaffold.py`** (389 lines): no templating engine — each scaffolded artifact is a module-level `_DEFAULT_*` triple-quoted string constant plus a small `_scaffold_*(sw_dir, created)` helper following one exact idiom: check `.exists()`, `mkdir(parents=True)` if the dir is missing (append a `"<path>/"` marker to `created`), then check-and-`write_text()` the file inside it (append the file's path to `created`). `_scaffold_templates()` (lines 257-266) is the closest analogue and the exact template to clone. `created: list[str]` is threaded through every helper and returned via `ScaffoldResult.created`. `scaffold_project()` (lines 333-388) is the orchestrator; the new call belongs at line 359, immediately after `_scaffold_templates(sw_dir, created)` and before `_scaffold_constitution(...)`.
- **`sw init`'s CLI output is already fully generic**: `interfaces/cli.py:77-78` does `for item in result.created: console.print(f"  Created: {item}")` — zero CLI code changes needed; the new scaffolded items print automatically.
- **`tach.toml`** (204 lines): the `[[interfaces]] from = ["specweaver.sandbox"]` block (lines 156-158) confirmed does **not** contain `execution.core` or `execution.core.atom.BashActionAtom` — SF-1 did not touch this file. Every sandbox submodule `core.flow` legitimately consumes is listed **twice** in the same `expose` array: once as a bare module entry (`"qa_runner.core"`) and once as the specific leaf-class entry (`"qa_runner.core.atom.QARunnerAtom"`) — same for `git.core`/`git.core.atom.GitAtom`, `code_structure.core`/`code_structure.core.atom.CodeStructureAtom`. SF-3 adds both `"execution.core"` and `"execution.core.atom.BashActionAtom"` the same way, into the same array.
- **`src/specweaver/core/flow/context.yaml`** (59 lines): `consumes:` (lines 18-31) confirmed does **not** contain `specweaver/sandbox/execution/core` — SF-1 did not touch this file either. Style confirmed slash-separated (`specweaver/sandbox/qa_runner/core`, not dotted). New line goes after `- specweaver/sandbox/mcp/core` (line 29), keeping the `sandbox/*` entries grouped together before `dispatcher`/`security`.
- **`src/specweaver/sandbox/execution/core/context.yaml`** (SF-1's own file): confirmed exactly one line, `archetype: adapter` — nothing for SF-3 to touch here; SF-3's job is the *consumer's* `consumes:` list (`core/flow/context.yaml`), not this file.
- **Backward compatibility — zero risk, confirmed by reading every existing scaffold test**: no test anywhere asserts a closed/exhaustive set of scaffolded files. The one test that iterates `.specweaver/`'s direct children, `test_marker_dir_has_no_config` (`test_scaffold.py:283-289`), only asserts `"config.yaml" not in children` — adding a `scripts/` sibling doesn't affect it. Existing tests only ever assert individual path existence (`assert (path).is_file()`), never a closed set.
- **Test patterns to clone**: `test_creates_templates_dir_with_component_spec` (`test_scaffold.py:38-46`, unit — creation + content assertions) and `test_does_not_overwrite_existing_template` (`test_scaffold.py:190-199`, unit — idempotency, pre-seed custom content then assert it's untouched after `scaffold_project()` runs again) are the exact structures to mirror. `test_init_creates_template` (`test_cli_projects.py:78-82`, CLI-level, `runner.invoke(app, ["init", ...])` then assert path existence) is the CLI-level equivalent to mirror.
- **`docs/architecture/03_system_topology/hard_dependency_rules.md`** (41 lines): the stale `flow` row (line 12) lists Consumes as `config, llm, review, implementation, planning, validation, sandbox/qa_runner, sandbox/dispatcher, sandbox/security, workspace/memory` — missing `sandbox/git`, `sandbox/code_structure`, `sandbox/mcp` (all three are live in the real `context.yaml`) and will be missing `sandbox/execution` once SF-3 lands. Corrected row (Consumes column): `config, llm, review, implementation, planning, validation, sandbox/git, sandbox/qa_runner, sandbox/code_structure, sandbox/mcp, sandbox/execution, sandbox/dispatcher, sandbox/security, workspace/memory` (Forbids column gets the same `sandbox/execution` addition to its exception list).
- **`docs/ORIGINS.md`** (Archon section, lines 170-182): line 176's bullet misattributes "Native CLI Action Nodes," `action:` as a discriminator key, and "FolderGrant" to Archon — verified during C-EXEC-02's design research that none of these three terms exist in Archon's actual codebase (it uses `bash:`/`script:` node fields instead, with a real `script: analyze-metrics` → `.archon/scripts/analyze-metrics.py` bare-name convention, which SpecWeaver's `AD-6` genuinely does mirror and should keep citing). Corrected bullet text (see Proposed Changes below) drops the false attribution while keeping the true one.
- **`docs/dev_guides/subprocess_execution.md`**: already has an "Engine-Internal Script Execution (BashActionAtom)" section (lines 80-87, written during SF-1's pre-commit) — it documents the Atom itself but never mentions where `.specweaver/scripts/` comes from. One sentence addition closes this, without touching the `action: bash` pipeline-syntax content that stays deferred to SF-2 (per the design doc's own Guide-1 status).
- **`docs/dev_guides/pipeline_engine_guide.md`**: confirmed zero mentions of `action: bash`/`.specweaver/scripts/` anywhere — correctly untouched by SF-3, consistent with the design doc's explicit deferral of Guide-1 to SF-2's pre-commit.
- **`docs/user_guides/1_installation_and_setup.md`** §4 "Initializing your First Project" (lines 37-47): enumerates what `sw init` scaffolds (`.specweaver/`, `CONSTITUTION.md`, `.specweaverignore`, `src/context.yaml`, `tests/context.yaml`) in one paragraph — will read as an incomplete/stale list once `.specweaver/scripts/` exists. User confirmed (Q1) this update is in scope for SF-3.

## Resolved Audit Findings

Both Phase 4 open questions resolved by explicit user confirmation ("yes, both A"):
1. `docs/user_guides/1_installation_and_setup.md` §4 gets an added clause for `.specweaver/scripts/`.
2. The drafted `.specweaver/scripts/README.md` content (see Proposed Changes) is approved as-is.

All other research questions were resolved directly against the live codebase — no further open questions.

## Proposed Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/workspace/project/scaffold.py` | `[MODIFY]` | New `_DEFAULT_SCRIPTS_README` constant + `_scaffold_scripts_dir()` helper + one new call in `scaffold_project()` |
| `tach.toml` | `[MODIFY]` | Add `"execution.core"` + `"execution.core.atom.BashActionAtom"` to the `specweaver.sandbox` interface's `expose` array |
| `src/specweaver/core/flow/context.yaml` | `[MODIFY]` | Add `- specweaver/sandbox/execution/core` to `consumes:` |
| `docs/architecture/03_system_topology/hard_dependency_rules.md` | `[MODIFY]` | Correct the stale `flow` row (Consumes/Forbids columns) |
| `docs/ORIGINS.md` | `[MODIFY]` | Correct line 176's Archon attribution |
| `docs/dev_guides/subprocess_execution.md` | `[MODIFY]` | One-sentence addition to the existing BashActionAtom section noting the scaffold origin of `.specweaver/scripts/` |
| `docs/user_guides/1_installation_and_setup.md` | `[MODIFY]` | One clause added to §4's scaffolding-artifact list |
| `tests/unit/workspace/project/test_scaffold.py` | `[MODIFY]` | New creation + idempotency tests |
| `tests/unit/workspace/project/interfaces/test_cli_projects.py` | `[MODIFY]` | New CLI-level creation test |

No new files. No changes to `src/specweaver/sandbox/execution/core/` (SF-1's own files) — SF-3 only edits the *consumer's* side of the boundary (`core/flow/context.yaml`) and the public interface allowlist (`tach.toml`).

## `.specweaver/scripts/README.md` content (approved, FR-10)

```markdown
# `.specweaver/scripts/`

Scripts referenced by `action: bash` pipeline steps (C-EXEC-02) live here.

Reference a script by **bare filename only** — `script: setup.sh`, never a
path. It is resolved as `.specweaver/scripts/<name>` and canonically
validated to stay inside this directory before every execution; anything
that would resolve outside it (traversal, symlink escape, absolute path)
is rejected.
```

## `ORIGINS.md` line 176 — corrected text (approved)

Before:
```
- **Native CLI Action Nodes** → Supporting `action: bash` deterministic steps in pipeline definitions to cleanly trigger pre-test scaffolding without involving the LLM. Enforces strict `FolderGrant` protection by physically restricting hooks to `.specweaver/scripts/`. (Phase 3.40b)
```

After:
```
- **Bash/Script DAG Nodes** → Inspired by Archon's `bash:`/`script:` node fields (e.g. `script: analyze-metrics` resolved to `.archon/scripts/analyze-metrics.py`), SpecWeaver's `action: bash` deterministic pipeline steps trigger pre-test scaffolding without involving the LLM, resolving bare script names against `.specweaver/scripts/`. "Native CLI Action Nodes" and "FolderGrant" are SpecWeaver's own coinages, not Archon terminology. (Phase 3.40b)
```

## `scaffold.py` — Implementation Sequence (pseudocode)

1. Add `_DEFAULT_SCRIPTS_README` module-level constant (the approved README content above).
2. Add `_scaffold_scripts_dir(sw_dir: Path, created: list[str]) -> None`, cloning `_scaffold_templates()`'s exact structure:
   - If `sw_dir / "scripts"` doesn't exist: `mkdir(parents=True)`, append `".specweaver/scripts/"` to `created`.
   - If `sw_dir / "scripts" / "README.md"` doesn't exist: `write_text(_DEFAULT_SCRIPTS_README)`, append `".specweaver/scripts/README.md"` to `created`.
3. In `scaffold_project()`, add `_scaffold_scripts_dir(sw_dir, created)` immediately after the existing `_scaffold_templates(sw_dir, created)` call (line 359).

No other function in `scaffold.py` needs to change — `ScaffoldResult`, `scaffold_project()`'s signature, and the CLI's generic `for item in result.created` loop all already support an arbitrary-length `created` list with no changes.

## Test Plan

| Test | File | FR | Asserts |
|------|------|-----|---------|
| `test_creates_scripts_dir_with_readme` | `test_scaffold.py` (new, mirrors `test_creates_templates_dir_with_component_spec`) | FR-10 | `scaffold_project(tmp_path)` → `.specweaver/scripts/README.md` is a file; content mentions "bare filename" and `.specweaver/scripts/` |
| `test_does_not_overwrite_existing_scripts_readme` | `test_scaffold.py` (new, mirrors `test_does_not_overwrite_existing_template`) | FR-10 | Pre-seed `.specweaver/scripts/README.md` with custom content, run `scaffold_project()`, assert content is untouched (idempotency) |
| `test_marker_dir_has_no_config` (existing) | `test_scaffold.py` | — | Re-run unchanged as a regression check — confirms adding `scripts/` doesn't trip the existing "no config.yaml in `.specweaver/`" assertion |
| `test_init_creates_scripts_dir` | `test_cli_projects.py` (new, mirrors `test_init_creates_template`) | FR-10 | `sw init` via CLI runner → `.specweaver/scripts/README.md` is a file |

## FR / NFR / AD Coverage

| ID | Covered by |
|----|-----------|
| FR-10 | `_scaffold_scripts_dir()` + its 3 tests |

No NFRs are assigned to SF-3 (all of NFR-1 through NFR-10 belong to SF-1's `BashActionAtom` runtime behavior, already implemented and committed). No ADs are assigned to SF-3 either — AD-1 through AD-6 are all `BashActionAtom`-level decisions from SF-1.

## Backlog (deferred, out of scope for SF-3)

- `docs/dev_guides/pipeline_engine_guide.md`'s `action: bash` pipeline-syntax section (Guide-1) — deferred to SF-2's pre-commit, since the pipeline capability doesn't exist until SF-2 lands.
- Actually wiring `core/flow` code to import `sandbox.execution.core.atom.BashActionAtom` — that's SF-2's job; SF-3 only makes the import tach-legal.

## Phase 5: Final Consistency Check

**5.0 Pre-check**: The single FR assigned to SF-3 (FR-10) is covered. No NFRs or ADs are assigned to this SF.

**5.1 Open questions**: None remaining — both Phase 4 items were resolved by explicit user confirmation.

**5.1a Agent Handoff Risk**: A fresh agent starting only from this document has the exact existing-code template to clone (`_scaffold_templates`, cited with line numbers), the exact call-site line to insert at, the exact `tach.toml`/`context.yaml` line-level diffs needed, the exact corrected text for both doc fixes, and the exact test patterns to mirror. Nothing is left for the `dev` skill to invent beyond mechanical cloning of an already-established pattern — this is the lowest-risk SF in the feature.

**5.2 Architecture and future compatibility**: No circular imports (this SF introduces zero new Python imports — pure filesystem I/O in `scaffold.py`, config-only edits elsewhere). `tach.toml`/`core/flow/context.yaml` edits are purely additive, matching the `qa_runner`/`git`/`code_structure`/`mcp` precedent exactly. Directly enables SF-2 (its stated dependency on SF-3's config edits) and keeps `hard_dependency_rules.md` from drifting further out of sync with reality.

**5.2a Architecture Principles**: **DDD** — stays within `workspace.project` (scaffolding) and pure config/doc edits; no bounded-context crossing. **KISS** — clones an existing, proven pattern exactly; no new abstraction. **DRY** — reuses the `_scaffold_*(sw_dir, created)` idiom rather than inventing a new one. **Hexagonal** — scaffolding is already the I/O edge; no change to that boundary. **Separation of Concerns** — one new helper, one new call site, one clear responsibility (create the scripts directory and its README).

**5.3 Internal consistency**: All 9 proposed files are tagged `[MODIFY]`, no `[NEW]` source files (only new test *cases* within existing test files). FR-10 maps to one concrete code element (`_scaffold_scripts_dir`) and 3 tests plus a regression check.

### Red/Blue Team Review (2 cycles run — proportionate to this SF's low risk/small size)

**Cycle 1**:
- 🔴 **LOW**: Does the new `_scaffold_scripts_dir` call ordering matter — could placing it before vs. after `_scaffold_templates` affect anything? **Blue**: INVALID — the two helpers operate on disjoint paths (`templates/` vs `scripts/`) with no shared state beyond appending to the same `created` list, whose order only affects cosmetic CLI-output ordering, not correctness. No fix needed.
- 🔴 **MEDIUM**: The `tach.toml` and `context.yaml` edits are configuration-only with no code yet exercising the new import path (SF-2 doesn't exist yet) — how do we know the edits are actually *correct* (not just plausible), given `tach check` can't exercise an import that doesn't exist? **Blue**: VALID, clarify: `tach check` validates `tach.toml` syntax and cross-references it against `context.yaml` declarations repo-wide regardless of whether any code currently imports through the new path — it will catch a malformed entry (e.g., wrong dotted path, missing sibling declaration) even before SF-2 exists. Added `tach check` as an explicit post-edit verification step (already implicit in the Test Plan's regression expectations; making it explicit here). Not a code fix, a verification-step clarification.
- 🔴 **LOW**: Should the `hard_dependency_rules.md` correction also fix the doc's other potential staleness beyond the `flow` row, given the design doc's research only checked that one row? **Blue**: VALID — ACCEPTED as out of scope: auditing the entire 41-line doc for unrelated staleness is a separate cleanup task, not something FR-10 or SF-3's stated scope calls for. Fixing only the row this feature's own edits touch (per the design doc's own Refactoring Opportunities entry) is the right-sized scope.

**Cycle 2**: Re-examined Cycle 1's responses plus a fresh pass — no new findings above the continuation threshold. Review converges.

**Corrections made**: none required code changes to the plan — Cycle 1's MEDIUM finding was a verification-step clarification (already implicit, now explicit), not a plan defect.

---

## HITL Gate — Approval Required

This plan is ready for your review. Summary: 9 modified files (zero new source files), all changes clone an already-proven existing pattern exactly, zero new import chains, zero backward-compat risk (confirmed by reading every existing scaffold test). Both Phase-4 judgment calls resolved per your "yes, both A". Red/Blue review ran 2 cycles, converged with no required plan changes.

Reply with approval to mark this plan `APPROVED` and proceed to the `dev` skill for SF-3's TDD implementation.

---

## Post-Implementation Notes (2026-07-14)

Implemented exactly as planned — all 9 files, no deviations, no bugs found (unlike SF-1, this sub-feature's small, mechanical, precedent-cloning nature meant TDD surfaced nothing unexpected). One addition beyond the original 2 planned tests: a third idempotency test (`test_creates_readme_when_scripts_dir_already_exists`) was added per this plan's own Red/Blue Cycle 1 finding, covering the "directory exists, README missing" branch. Final test count: 4 new tests (3 unit + 1 CLI), all passing, 0 regressions across the full 5086-test suite.
