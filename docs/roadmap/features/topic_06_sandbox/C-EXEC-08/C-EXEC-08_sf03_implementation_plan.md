# Implementation Plan: Project Doc Policy [SF-03: Generated blocks]
- **Feature ID**: C-EXEC-08
- **Sub-Feature**: SF-03 — Generated blocks
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-08/C-EXEC-08_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-08/C-EXEC-08_sf03_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-19

**FRs owned**: FR-3 · **ADs**: AD-2 · **NFRs**: NFR-3 (a block never opens a protected file) ·
**Depends on**: SF-01 (committed f0ca523e); uses SF-02's merge (committed 47174ac5)

## Shape

| Piece | Where | Tag |
|---|---|---|
| `fill_block(text, name, body) -> str`: the text with the body between `<!-- sw:block NAME -->` and `<!-- sw:end NAME -->` replaced; raises naming both markers when either is missing, doubled or out of order | `core/config/doc_policy.py` (beside `DocBlock`) | NEW |
| `outside_blocks(text, names) -> str`: the text with those blocks' bodies emptied — what the script may not change. Never raises: a text without the markers comes back as it is | `core/config/doc_policy.py` | NEW |
| `DocPolicy` refuses two blocks naming one step, or one `file` + `name` twice, naming the line (Q1) | `core/config/doc_policy.py` | MODIFY |
| `BashActionAtom` exports `stdout_truncated: bool` beside the cut `stdout` (Q2) | `sandbox/execution/core/atom.py` | MODIFY |
| After a `bash` step passes, the `[[docs.block]]` whose `step` is this step's name gets the script's stdout as its body; the step fails, naming the file, when the markers are wrong, the stdout holds a marker, the stdout was cut (Q2), or the file resolves outside the project. Read and written with `newline=""`, so line endings stay | `core/flow/handlers/bash_action.py` | MODIFY |
| Before the first step, the run is refused, naming the block, when its `step` names a step of this pipeline that is not a `bash` step (Q3), or its `file` holds a protected name (`sandbox.security.PROTECTED_NAMES`, NFR-3) | the runner's start (`core/flow/engine/`) | MODIFY |
| The merge keeps a block file changed by its block's step when nothing outside its blocks changed (`outside_blocks(HEAD) == outside_blocks(staged)`, the file compared case-blind); a file new on the branch is not block-only; otherwise the file is judged as in SF-02 — for `README.md`, a proposal | `sandbox/git/core/worktree_ops.py` (reads both versions with `git show`, added to the engine whitelist) | MODIFY |

### The block's text

The markers stay; the body is the stdout without its trailing newline, on its own lines:

```
<!-- sw:block counts -->
<stdout>
<!-- sw:end counts -->
```

A stdout that holds either marker of its block fails the step: it would close the block early and
write past it.

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | `fill_block`, `outside_blocks`; the bash handler fills; the run-start check | FR-3 (fill, markers missing, no LLM step) | a block step's output reaches no file |
| CB-2 | the merge keeps a block-only change by its step | FR-3 under worktree isolation, AD-2 | the block step's `README.md` change becomes a proposal |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit | `DocPolicy`: two blocks for one step, or one block twice, refused naming the line. `fill_block`: replaces only the body; the rest byte for byte; markers missing, doubled, end before start → error naming both; a stdout holding a marker → error; an empty stdout → an empty body. `outside_blocks`: two texts that differ only inside the block are equal; outside, not |
| CB-1 | integration | a real `bash` step named by a block, no isolation: the block of `README.md` holds the script's stdout, the rest unchanged; a file without the markers fails the step, naming them; another `bash` step does not fill it; a pipeline whose block step is a `generate` step is refused before any step runs; a block on `context.yaml` is refused; a cut stdout fails the step and writes nothing; a `README.md` that is a symlink out of the project fails the step |
| CB-1 | e2e | `sw run` of a pipeline with `update_counts` (prints a count) on a project whose `README.md` has the markers: the count is in the block, and the run completes |
| CB-2 | integration | real git, per-step worktree and session: the block step's change lands; a block step whose script also edits `README.md` outside the block → proposed, not kept; another step that changes the block → proposed |
| CB-2 | e2e | the CB-1 journey with `use_worktree: true` on the step: the block lands through the merge |

## Mutants (into `C-EXEC-08_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the missing-marker check; the marker-in-stdout check; the cut-stdout check; the protected-file check; the handler fills every step's blocks (step not compared); the run-start check | CB-1 unit + integration |
| CB-2 | the outside-the-block comparison dropped (any change by the block's step kept); the block's step not compared at the merge | CB-2 integration |

## Research Notes

- A `bash` step's stdout reaches the handler as `result.exports["stdout"]`, cut at 1 MiB with
  `...[TRUNCATED]` appended (`sandbox/execution/core/atom.py:23,46-51,160-169`) — Q2.
- The handler binds the script's cwd to `isolation.execution_root or project_path`
  (`bash_action.py:62-73`); the block is written there too, so under isolation it reaches the
  merge like any change.
- `DocBlock(file, name, step)`, name `[a-z0-9_-]+` (`core/config/doc_policy.py:59-74`), so a name
  cannot break the marker syntax.
- The pipeline is validated at load (`parser.py:58`, `validate_flow`), where no policy is known;
  the block-step check therefore runs at the run's start, where `isolation.doc_policy` is set.
- `git show HEAD:<file>` and `git show :<file>` read the two versions at the merge; `show` is
  read-only and joins `log` on the engine whitelist (`sandbox/git/core/atom.py:42-62`).
- Without worktree isolation a script writes the real repo itself (SF-02 note); AD-2 then holds only
  for what SpecWeaver writes — the merge is what enforces it under isolation.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | May two blocks name the same step? | no: one step fills one block; a second is refused when the settings load `[agreed 2026-10-19]` |
| Q2 | A stdout over 1 MiB is cut: what then? | the step fails naming the size, and nothing is written `[agreed 2026-10-19]` |
| Q3 | A block names a step of this pipeline that is not a `bash` step? | the run is refused before any step, naming both `[agreed 2026-10-19]` |

## Backlog

none
