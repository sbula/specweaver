# Design: Project Doc Policy

- **Feature ID**: C-EXEC-08
- **Epic**: Topic 06 (Sandbox)
- **Status**: APPROVED by the user 2026-10-19
- **Origin**: `E-SENS-03` plan Q2, parked 2026-10-16 for the laptop; minted 2026-10-17; grilled with
  the user 2026-10-19 (Q1–Q7).

| | |
|---|---|
| Uses | `E-SENS-03` (the task grant) · `D-EXEC-02` (the worktree merge) · `C-FLOW-13` (the project's `specweaver.toml`) · `D-FLOW-01` (pipeline steps) |
| Enables | `C-FLOW-11` — an agentic coder that may write |
| Not touched | what an agent may *read* · the protected files (`context.yaml`, `.env`, `.git`, `.specweaver`) · files SpecWeaver itself writes outside an agent's step |

## Feature Overview

Each project says, in its own `specweaver.toml`, which docs agents may change and how — instead of
one rule in code. Today `sandbox.security.merge_keeps` treats `README.md` and `docs/` as never
changeable by an agent, for every project; a README's test counts therefore need a person each
time, and a project that wants agents to keep its user guide current cannot say so. A doc change
an agent may not make is today discarded at the merge; from now on it is kept as a proposal.

## Research Findings

### Codebase Patterns

- The one rule: `merge_keeps(path, allowed)` (`sandbox/security.py:220`) — `doc_updates.md` always
  kept, `README.md` and `docs/` never, the rest by the task's allow-list (`path_allowed`, `**` and
  `*` globs). Two callers: the task grant `TaskGrant.covers` (`security.py:175-200`, built in
  `sandbox/dispatcher.py:204`) and the worktree merge `_strip_forbidden_files`
  (`sandbox/git/core/worktree_ops.py:125-145`), which restores or deletes a stripped file — the
  change is lost.
- A project's `specweaver.toml` is read by `core.config.bootstrap` and parsed strictly in
  `core.config` (`parse_project_llm`, `llm_settings.py:272`): the place for a `[docs]` section.
- Pipeline steps have names (`D-FLOW-01`); a `bash` step runs a project script
  (`.specweaver/scripts/`).

### External Tools

None. The rule order is `.gitignore`'s: the last matching line wins.

### Blueprint References

`.gitignore` (last match wins), `CODEOWNERS` (paths to owners).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | The policy is the project's | Settings loader | SHALL read the doc policy from the `[docs]` section of the project's `specweaver.toml` `[agreed 2026-10-19]` | every clone of a project follows the same rules, reviewed like code |
| FR-2 | Three kinds of path rule | Policy | SHALL give each path one access: `human` (no agent changes it), `open` (any agent step may), or `step` (only the named steps may) `[agreed 2026-10-19]` | a roadmap stays human, a user guide can stay current |
| FR-3 | Generated blocks | Policy, runner | SHALL let a named `bash` step replace one marked block inside a file — its standard output becomes the block — and no LLM step ever `[agreed 2026-10-19]`; a file without the block's markers fails the step, naming them | a README's counts update with no person, and the rest of the README stays human |
| FR-4 | Steps by name | Policy | SHALL name the steps of a `step` rule or a block by their pipeline step name `[agreed 2026-10-19]` | exactly the intended step gets the right, not every step of a kind |
| FR-5 | Last match wins | Policy | SHALL decide a path by the last rule whose pattern matches it `[agreed 2026-10-19]` | a folder can be opened and a part of it closed |
| FR-6 | No section, no change | Policy | SHALL, for a project without `[docs]`, keep today's rule: `README.md` and `docs/**` human, the rest by the task's grant `[agreed 2026-10-19]` | nothing changes for a project that does not opt in |
| FR-7 | A refused change is a proposal | Merge | SHALL keep each doc change an agent may not make as a proposal in `doc_updates.md`, and the run goes on `[agreed 2026-10-19]` | no wanted change is lost, and no person is interrupted |
| FR-8 | One rule, two places | Grant, merge | SHALL decide a write through the task grant and through the worktree merge by the same policy, for the step that wrote it | an agent is never told it may write what the merge then throws away |

`FR-7` is new behaviour: today a stripped file is restored or deleted, and the change is lost.
`FR-8` is a **seam FR** across `E-SENS-03` and `D-EXEC-02`, proven at integration tier.

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | the project's settings text | `core.config.bootstrap` · the `specweaver.toml` reader | read `llm_settings.py:252-280` (`ProjectLlmSection`, `parse_project_llm`) |
| FR-3, FR-4 | the running step's name and action | `D-FLOW-01` · the pipeline step | read `sandbox/dispatcher.py:204` (where the grant is built) |
| FR-7, FR-8 | the file a merge would strip | `D-EXEC-02` · `_strip_forbidden_files` | read `sandbox/git/core/worktree_ops.py:125-145` |
| FR-8 | the grant's decision | `E-SENS-03` · `TaskGrant.covers` | read `sandbox/security.py:175-200` |

## Non-Functional Requirements

| # | NFR | Rule |
|---|---|---|
| NFR-1 | A broken policy refuses | An unknown key, access or a pattern holding `..` or an absolute path stops the command, naming the line, like the other settings |
| NFR-2 | Nothing is lost | A refused change always reaches `doc_updates.md`, also when that file did not exist |
| NFR-4 | One pattern language | Rule patterns are the task grant's: `*` stays in one folder, `**` spans folders (`path_allowed`) |
| NFR-3 | The policy cannot widen the walls | No rule makes `context.yaml`, `.env`, `.git` or `.specweaver` writable |

## Settings shape `[agreed 2026-10-19]`

```toml
[[docs.rule]]
paths = ["docs/user_guides/**"]
access = "open"                 # human | open | step

[[docs.rule]]
paths = ["docs/api/**"]
access = "step"
steps = ["update_api_docs"]

[[docs.block]]
file = "README.md"
name = "counts"
step = "update_counts"           # a bash step; its output fills the block
```

In the file, a block is marked `<!-- sw:block counts -->` … `<!-- sw:end counts -->`.

## External Dependencies

None.

## Architectural Decisions

| # | Decision | Why |
|---|---|---|
| AD-1 | The policy is parsed in `core.config` and handed to `sandbox.security`, which decides | `sandbox` may not reach the settings files; one decider serves grant and merge (FR-8) |
| AD-2 | A block is written by SpecWeaver from the step's output; the script never edits the file | the script cannot touch what is outside its block |

## ROI Analysis

### Investment Cost

Three sub-features: the policy, its use in grant and merge, and blocks.

### Returns

`C-FLOW-11` can let an agent write; a README's counts stop needing a person; refused changes stop
being lost.

### Risk Assessment

| Risk | Mitigation |
|---|---|
| A rule opens too much | `human` stays the default for README and `docs/`; NFR-3 keeps the protected files closed |
| A script prints something wrong into the README | only its own block changes, and the diff is reviewed with the commit |

### Refactoring Opportunities

`merge_keeps` becomes the policy's decision; its two callers pass the step.

## Developer Guides Required

The user guide gains a "Which docs agents may change" section with the example above.

## Non-Goals

- What agents may read.
- Rules per user or per role outside a pipeline step.

## Sub-Feature Breakdown

### SF-01: The policy

FR-1, FR-2, FR-4, FR-5, FR-6. Input: the `[docs]` text. Output: a policy that answers "may step S
change path P?".

### SF-02: Grant and merge follow it

FR-7, FR-8. Input: the policy and the running step. Output: grants and merges by the policy; refused
changes as proposals.

### SF-03: Generated blocks

FR-3. Input: a block rule and a `bash` step's output. Output: the block replaced, nothing else.

## Execution Order

SF-01, then SF-02 and SF-03.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | The policy | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-02 | Grant and merge follow it | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-03 | Generated blocks | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Now**: design approved 2026-10-19.
**Next**: the SF-01 plan.
