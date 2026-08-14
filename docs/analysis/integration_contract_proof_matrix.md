# Integration-contract proof matrix

`TECH-017` SF-01. CB-1 built the skeleton; **CB-2 assessed `INT-US-28` and CB-3 `INT-US-21`** — their claims below
carry verdicts and evidence. The other 11 entries remain `unassessed` pending SF-02/03.

For every delivered integration contract, what it *claims* versus what a test *proves*. One claim
is **one assertion about behaviour at a seam**, not one sentence (`SF-01` D-1) — otherwise verdicts
are not comparable between entries.

> [!IMPORTANT]
> **What a verdict will mean.** `proven` names the **test function**, not the file: a file-level
> citation is what let 8 of `INT-US-21`'s 10 requirements be credited to a file asserting nothing
> about it. `unproven` means no such function exists. `unprovable` means the claim cannot be tested
> as written — recorded, never re-worded, because a delivered contract is immutable (`NFR-1`).
>
> **An `unproven` verdict is not a ticket.** The boundary that finds one cites an existing test
> after reading it, or writes the missing integration/e2e test. A ticket is filed only where a
> decision is needed that the auditor cannot take.

## Coverage at a glance

| Entry | Proof files | Tests | Tiers | Claims |
|---|---|---|---|---|
| `INT-US-01` | 1 | 5 | e2e | 3 |
| `INT-US-02` | 1 | 7 | e2e | 2 |
| `INT-US-03` | 2 | 7 | e2e, integration | 8 |
| `INT-US-04` | 1 | 4 | e2e | 2 |
| `INT-US-05` | 1 | 6 | e2e | 2 |
| `INT-US-05-SF03` | 0 | 0 | — | 1 |
| `INT-US-05-SF04` | 0 | 0 | — | 1 |
| `INT-US-09` | 1 | 5 | e2e | 11 |
| `INT-US-21` | 3 | 61 | e2e, integration | 8 |
| `INT-US-21-SUB` | 0 | 0 | — | 1 |
| `INT-US-24` | 2 | 13 | e2e, integration | 6 |
| `INT-US-25` | 9 | 75 | e2e, integration | 13 |
| `INT-US-28` | 9 | 88 | integration, unit | 6 |

**13 entries, 64 claims, 271 tests across 30 cited files.** The count has risen twice as contracts
were re-read in full: +4 in SF-01 CB-3 (`INT-US-21`), +11 in SF-02 CB-1 (below). Counts for the 6
still-unassessed entries are CB-1's and remain **lower bounds** until SF-03 re-reads them.

### SF-03 CB-1 — re-extraction of the last three, 2026-08-14

| Entry | Description | Was | Now | What CB-1 had missed |
|---|---|---|---|---|
| `INT-US-25` | 249 words | 9 | **13** | the `sw constitution init/show/check` surface; *five* preset bundles; `extends: validation_spec_default` inheritance resolving in the same round trip; and the **exclusion** of `C-VAL-03`'s code-level half, delegated to `TECH-041` |
| `INT-US-24` | 93 words | 3 | **6** | the declared stage chain incl. arbiter fault attribution; execution on top of the shipped US-3 loop; and the **exclusion** of DAL escalation, delegated to `C-EXEC-07` |
| `INT-US-02` | 32 words | 2 | 2 | nothing — one sentence, two assertions |

**The length predictor has now held three times.** One-sentence descriptions were extracted
correctly every time; multi-sentence ones never were. It is a usable rule for any future audit: read
long contracts twice, and expect the second reading to find an exclusion, because both entries that
grew here hid one in their final sentence.

**Exclusions keep being the thing that is missed.** `INT-US-03` C7, `INT-US-24` C6 and `INT-US-25`
C13 are all *"X is deliberately delegated elsewhere"* — falsifiable, load-bearing for scope, and
invisible to an extractor reading only the opening assertion.

### SF-02 CB-1 — re-extraction of the five thin entries, 2026-08-14

| Entry | Was | Now | Where the missing claims were |
|---|---|---|---|
| `INT-US-09` | 3 | **11** | CB-1 read only the **Status** paragraph. The entire Integration Description — the `SubprocessExecutor` boundary rebound to the worktree, bash *and* QA bounded, Main-Branch-Wins strip-merge, out-of-bounds hunks stripped, opt-in policy at the composition root, default-off byte-identical — was unextracted |
| `INT-US-03` | 5 | **8** | the `D-INTL-01` → `D-VAL-01`/`D-VAL-05` pipe; the **exclusion** of container/Podman; DAL-driven auto-escalation from the Status paragraph |
| `INT-US-01` | 3 | 3 | complete — the contract is one sentence |
| `INT-US-04` | 2 | 2 | complete — one sentence |
| `INT-US-05` | 2 | 2 | complete — one sentence |

**Under-extraction is not uniform, and that matters for SF-03.** Three of these five were already
complete; the two that were not account for the entire +11. The pattern is length: a one-sentence
Integration Description was extracted correctly, a multi-sentence one was not, and `INT-US-09` — the
longest contract in the tree — was read from the wrong paragraph entirely.

**Exclusions are claims.** `INT-US-03` C7 records that container execution is out of scope. A
contract asserting *"X must not happen"* is falsifiable, so it earns a verdict like any other.


## `INT-US-01` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/assurance/test_standards_e2e.py` | e2e | 5 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The CLI parses the target file using Loom (`E-SENS-01`). | `proven` | e2e — `test_validate_only_all_rules_fire` in `test_validation_pipeline_e2e.py` drives `sw check` over a real spec. **Cited after reading; NOT the contract's own cited file** (FR-4). *"using Loom"* is a component attribution, not observable from outside the CLI, so only the parse itself is witnessed. |
| C2 | The CLI passes the parsed result to the Validation Engine (`E-VAL-01`). | `proven` | e2e — same test: every `S01`–`S11` rule id appears in the output, which can only happen if the parsed spec reached the Validation Engine. |
| C3 | No unvalidated LLM generation can occur. | `unprovable` | A system-wide universal negative over **data-defined** pipelines. D-3 finds no structural invariant to guard: pipelines are YAML and a user may author one freely. `scenario_validation.yaml` ships `generate_scenarios` (`action: generate`) with **no VALIDATE step at all**, so a guard would have to encode a meaning of *"unvalidated"* the contract never fixes. Recorded, not re-worded (NFR-1). |

## `INT-US-02` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/workflows/test_drafter_loop_e2e.py` | e2e | 7 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The interactive loop (`E-INTL-02`) hands the generated context to the Review Engine. | `unassessed` | — |
| C2 | No manual copy-pasting is required between the two. | `unassessed` | — |

## `INT-US-03` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/sandbox/test_implement_loop_worktree_isolation_e2e.py` | e2e | 2 |
| `tests/integration/interfaces/cli/test_cli_implement_isolation.py` | integration | 5 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `sw implement` generates code **and** tests. | `unproven` | The cited e2e **fakes generation** with a bash script (`gen.sh`), so `D-INTL-01` never runs. Only the pipeline's declared shape is tested — `test_generate_steps_unchanged` (**unit**). |
| C2 | It runs the generated tests. | `proven` | e2e — `test_dal_b_escalation_runs_generated_qa_bounded_and_reconciles` runs real pytest over the freshly written code. |
| C3 | It runs code rules C01-C08. | `unproven` | No test runs `validate_code`. Only its declaration — `test_validate_code_targets_generated_code_report_only` (**unit**). |
| C4 | It auto-fixes lint, all in one autonomous loop. | `unproven` | No test runs the loop. Only its shape — `test_lint_fix_runs_before_run_tests`, `test_run_tests_has_loopback_gate` (**unit**). The loop-back has never been observed to loop. |
| C5 | QA/test execution runs **exclusively** inside the US-9 zero-trust worktree sandbox, container-free. | `proven` | e2e — worktree-bounded QA in `test_dal_b_escalation_runs_generated_qa_bounded_and_reconciles`; *container-free* by C7's guard. |
| C6 | The Implementation Generator (`D-INTL-01`) pipes natively into the QA Runner (`D-VAL-01`) **and** the Code Validation Rules (`D-VAL-05`). | `unproven` | The pipe is a pipeline declaration, tested as such at **unit** tier (`test_pipeline_has_five_steps_in_order`). No test drives `D-INTL-01` into `D-VAL-01`/`D-VAL-05`. |
| C7 | **Exclusion:** container/Podman execution (`D-EXEC-01` / `B-EXEC-01`) is OUT of scope for this base contract — no container code path is reachable from the implement loop. | `proven` | integration — `test_container_execution_mode_stays_dormant_on_implement`, **written at this boundary**. **Probed:** adding a `use_container` field to `IsolationPolicy` fails it. |
| C8 | Untrusted high-assurance (DAL_A/B) code is executed worktree-bounded via **DAL-driven auto-escalation**; small/non-git projects stay on host. | `proven` | integration — the five DAL cases in `test_cli_implement_isolation.py`, plus the e2e DAL_E control `test_low_dal_project_runs_on_host_and_probe_fails`. |

### Finding: the autonomous loop is proven as a **shape**, never as a loop

Four of eight claims — C1, C3, C4, C6 — are unproven, and all four fail for the same reason. The
contract's core promise is that *"`sw implement` generates code + tests, runs the tests, runs
C01–C08, and auto-fixes lint **in one autonomous loop**."* What exists is:

* `test_implement_pipeline.py` (**unit**) — the pipeline *declares* five steps in order, `lint_fix`
  before `run_tests`, a loop-back gate on `run_tests`, report-only `validate_code`. Structure only.
* `test_implement_loop_worktree_isolation_e2e.py` (**e2e**) — real, but it **substitutes a bash
  script for `D-INTL-01`**, so generation never happens and only the isolation half is exercised.

Between them: the loop has never been observed to loop, `validate_code` has never been observed to
run, and the `D-INTL-01 → D-VAL-01/D-VAL-05` pipe has never carried anything. This is the exact
shape the 2026-07-26 review meant by *"happy-path only / cites capability suites"*, and it is a
larger gap than anything SF-01 found: `INT-US-28`'s seam was proven in two halves that met at a
mock, whereas here the central journey has no end-to-end proof at all.

**Not closed at this boundary.** Writing it means a scripted-LLM e2e driving `sw implement` through
generate → lint_fix → run_tests → validate_code including a loop-back iteration, with real `ruff`
and real `pytest`. The harness pattern exists (`ScriptedLLM` / `scripted_world` in
`test_feature_decomposition_e2e.py`) but is file-local and would need extracting. That is a
sub-feature's worth of work, not a boundary's, so it was escalated as SF-02's one decision (NFR-3)
and **scoped as `TECH-017` SF-04 on 2026-08-14** — not filed as a ticket, and not left as a note.

The four verdicts stay `unproven` until that sub-feature closes them — the honest state, because
the claims are not disproven, they are unwitnessed.

### FR-6 — capability findings

C1 and C6 trace to `D-INTL-01` (Implementation Generator): it has no test that drives it into the QA
runner. C3 traces to `D-VAL-05` (Code Validation Rules) — `validate_code` is declared and never
exercised through the loop. Recorded against those capabilities; `SF-03` consolidates.

## `INT-US-04` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/assurance/test_mcp_flow_e2e.py` | e2e | 4 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The SQLite Config DB (`E-FLOW-01`) statefully persists Validation Engine outputs. | `unproven` | The cited file never mentions validation, persistence or artifact events (measured: 0 occurrences of `validation`, `persist`, `ValidationResult`, `artifact_events`). Nothing found elsewhere that persists **Validation Engine** outputs to the config DB. |
| C2 | The Pipeline Runner passes sanitized, verified context into subsequent prompt steps. | `unproven` | Split claim, and only half is witnessed. Context reaching subsequent prompt steps is proven by `test_mcp_flow_e2e_fetch` (the Pre-fetch Context Assembler). *Sanitized, verified* is not: 0 occurrences of `sanitiz` in the cited file, and the verification half depends on C1, which is unproven. |

## `INT-US-05` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/core/test_lineage_e2e.py` | e2e | 6 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The AST Skeleton Extractor resolves edges against the Git Worktree Bouncer. | `unproven` | The cited file is about `# sw-artifact` tag survivability. Measured: `skeleton`, `worktree`, `extractor` each appear **0 times**. The `D-SENS-02` ↔ `D-EXEC-02` seam this claim names is not exercised anywhere in it. |
| C2 | Extracted context reflects the current filesystem state, with no hallucinatory paths. | `unproven` | Same file; the claim is about extracted context matching filesystem state, and nothing there resolves AST edges against a worktree. Not found proven elsewhere. |

### Finding: the thin trio cite proof for a different subject

The 2026-07-26 review flagged these entries as *"citing capability suites"*. Measured, it is worse
than that — **the suites they cite are not their capability's**:

| Entry | Claims | Its cited proof actually tests | Subject-word count in the cited file |
|---|---|---|---|
| `INT-US-01` | CLI parses via Loom → Validation Engine | the standards scan → show → clear lifecycle (`E-VAL-02`) | `Loom` 0 · `parse` 0 · `validate_spec` 0 |
| `INT-US-04` | config DB persists Validation Engine outputs | the Pre-fetch Context Assembler (MCP flow) | `validation` 0 · `persist` 0 · `sanitiz` 0 |
| `INT-US-05` | AST Extractor resolves edges vs the Worktree Bouncer | `# sw-artifact` tag survivability | `skeleton` 0 · `worktree` 0 · `extractor` 0 |

Every one of those counts is a measurement, not an impression. `INT-US-01`'s two observable claims
were recovered by citing `test_validation_pipeline_e2e.py` after reading it (FR-4) — it was never
the contract's own citation. For `INT-US-04` and `INT-US-05` no such file was found: **four claims
stand `unproven` with no candidate anywhere in the tree.**

**The Verifiable Proof field is part of the delivered contract and is not re-worded (NFR-1).** The
mis-citation is recorded here, which is the whole purpose of the matrix.

### Fixed at this boundary: the `INT-US-05` width-flake

`test_sw_check_lineage_flag_detects_orphans` asserted on Rich-rendered output, so soft wrapping made
it width-dependent — `COLUMNS=80` failed while 60/100/200 passed, and 40 broke a second assertion.
Now compared through a `_shows()` helper that squashes whitespace on **both** sides. Verified
width-independent at COLUMNS 20/40/60/80/100/200.

**R-2 checked before editing:** the rendered output contained the full path broken across a line
(`orp\nhan.py`), not a truncated one, so this is a renderer artefact and not a product defect.
`git diff` confirms `src/` is untouched.

### Mutation run, 2026-08-14 — the four claims, measured instead of grepped

`scripts/_mutate_campaign.py`, full suite per mutant, 3m21s. CB-4's verdicts rested on
subject-word counts (*"`worktree` appears 0 times"*), which is absence of evidence. This changes
each behaviour and asks whether anything objects.

| Claim | Mutant | Result |
|---|---|---|
| `INT-US-04` C1 — the config DB persists Validation Engine outputs | **none possible** | see below |
| `INT-US-04` C2 — the runner passes context into subsequent prompt steps | assembler always returns empty | `KILLED` ×2 |
| `INT-US-05` C2 — extracted context reflects the filesystem | skeleton content replaced by a constant | `KILLED` ×1 |
| `INT-US-05` C1 — the extractor resolves edges against a bounded root | containment root widened to `project_path.parent` | **`SURVIVED`** |

**`INT-US-04` C1 has nothing to mutate.** The config DB's tables are `flow_artifact_events`,
`llm_*`, `memory_*` and `workspace_*`. **There is no table for validation output**, and
`ValidationResult` does not appear in `src/` at all. The claim is not unproven-but-built; the
persistence surface it names does not exist. That settles the escalated question for this half.

**`INT-US-05` C1 survived, and the mutant is not equivalent — checked before recording.**
`cwd` is not decorative: it constructs `FileExecutor(cwd=...)`, whose `_cwd` **is the containment
root** — `candidate = (self._cwd / path).resolve()` then `candidate.relative_to(self._cwd)` is the
traversal guard, and the class docstring says *"path traversal is always prevented"*. Widening it by
one directory lets the skeleton extractor read outside the project root, and **not one of 6853 tests
noticed**. Production passes the right value; nothing would catch a regression that stopped.

**The two kills are narrower than they look.** Both killers are unit tests of the assembler function
itself (`test_context_assembler.py`). So the *function* is protected — but `INT-US-04` C2's claim is
about the **runner passing context into subsequent prompt steps**, and no test died at that seam.
The kill confirms the assembler works, not that the contract's journey does. Verdict unchanged.

**All four verdicts stood at the time of the run.** Three rested on a measurement and the fourth on
the absence of a database table rather than the absence of a grep hit.

### Chasing the survivor found a live defect, 2026-08-14

`INT-US-05` C1's survivor was **not** a coverage gap. `evaluate_and_fetch_skeleton_context` read
`res.exports["skeleton"]` while `CodeStructureAtom._handle_structure` exports `"structure"`
(`atom.py:127`). The condition never held, so the assembler **returned `{}` for every caller** —
and it is called from `generation.py` and twice from `review.py`. **Skeleton context has never
reached a generation or review prompt.**

That is why the containment mutant survived: the result was discarded before the containment root
could matter. The three existing tests in `test_context_assembler.py` all mock `CodeStructureAtom`
and hand back `{"skeleton": ...}`, so the mock and the bug agreed with each other and disagreed with
production.

**Fixed in place** (`AD-2`), with the mocks corrected to the atom's real contract and a real-atom
test added that asserts **both** halves — that a file inside the root IS returned, and one outside
is not. The first version of that test asserted only the second half, which an empty result
satisfies, so it passed while proving nothing; asserting the inside half is what stops it going
vacuous if the feature dies again.

`INT-US-05` C1 is now `proven`: re-running the original mutant reports `KILLED`. C2's verdict is
unchanged — its only killer remains a mocked unit test.

**This is the clearest result the audit has produced.** Reading the contract, grepping its cited
proof, and counting subject words all said *unproven*. Only changing the code and watching nothing
object led to the reason: a feature wired to a key that does not exist, green in CI for as long as
the mocks have existed.

### A second decision escalated by this sub-feature

`INT-US-04` C1/C2 and `INT-US-05` C1/C2 have **no proof and no candidate**. Unlike `INT-US-03`'s
gap — where the loop exists and is merely unwitnessed — here it is not established that the claimed
integrations were ever built. Writing tests would be the wrong first move: the prior question is
whether `D-SENS-02` ↔ `D-EXEC-02` edge resolution, and Validation-Engine-output persistence, exist
at all. That is a scope question, so it is named rather than answered (FR-5, NFR-3).


## `INT-US-05-SF03` — Intelligent Code Exclusions

**No test file cited.** Frozen in `scripts/baselines/proof_tier.json` with a named owner.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The `.specweaverignore` engine feeds deterministic exclusions into the Extractor. | `unassessed` | — |

## `INT-US-05-SF04` — Framework Native Understanding

**No test file cited.** Frozen in `scripts/baselines/proof_tier.json` with a named owner.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The Macro Evaluator detects framework context boundaries natively. | `unassessed` | — |

## `INT-US-09` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/sandbox/test_step_worktree_isolation_e2e.py` | e2e | 5 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | Per-step worktree isolation works for the single-step case. | `proven` | e2e — `test_explicit_use_worktree_runs_bash_bounded_to_worktree`, `test_policy_enforced_runs_bash_bounded_to_worktree`, `test_run_tests_pytest_executes_bounded_to_worktree`. |
| C2 | Session mode runs a whole untrusted span in one worktree with a single authorized reconcile. | `proven` | integration — `test_session_persists_file_across_steps` (one worktree across steps), `test_explicit_use_worktree_step_still_shares_session_worktree`. **Cited after reading; not in `INT-US-09`'s own proof file** (FR-4). |
| C3 | The legacy per-step model remains single-step-only — a documented limitation, not a defect. | `unprovable` | A scope statement about what is **not** supported, not a behaviour. Pinning it with a test would freeze a known limitation as required behaviour — the test would have to assert a multi-step per-step run keeps failing. Recorded, not tested. Contract not re-worded (NFR-1). |
| C4 | `D-EXEC-02`, `E-EXEC-01` and `C-EXEC-02` are wired into **one** enforceable, container-free host-execution flow. | `proven` | e2e — the cited file drives bash (`C-EXEC-02`) and pytest QA through a worktree (`D-EXEC-02`) via `SubprocessExecutor` (`E-EXEC-01`) in one flow. *Container-free* shares its invariant with `INT-US-03` C7. |
| C5 | Untrusted execution runs inside an **ephemeral** git-worktree sandbox. | `proven` | e2e — `test_isolated_run_keeps_the_boundary_and_leaves_no_worktree`, **written at this boundary**. Teardown was proven for the git primitive (`test_git_atom.py`) and for *session* mode only; the per-step flow this contract describes had none. **Probed:** skipping the `git worktree remove` call fails it. |
| C6 | The `SubprocessExecutor` security boundary — credential stripping, resource limits, `cwd` containment — is **rebound to the worktree path**. | `unprovable` as written | Only **`cwd` containment** is path-dependent and it is proven (C1). Credential stripping and resource limits **cannot be rebound** — they apply on every path. **Probed:** the same script run **un-isolated** also reports the credential absent, so no assertion under isolation can distinguish a correct rebind from no isolation at all. The regression guard that the allow-list survives the rebind is in the new test and is deliberately **not** cited as proof. The contract asserts three things are rebound where one is; not re-worded (NFR-1). |
| C7 | Bash actions **and** QA execution both operate worktree-bounded rather than against the real source root. | `proven` | e2e — bash in `test_explicit_use_worktree_runs_bash_bounded_to_worktree` and QA in `test_run_tests_pytest_executes_bounded_to_worktree`; both surfaces, same file. |
| C8 | Source changes are reconciled back via the existing "Main-Branch Wins" strip-merge. | `proven` | **unit** — `test_success_strip_allowed`, `test_strip_merge_preserves_doc_updates` in `test_git_atom.py`. Tier diagnostic below. |
| C9 | Out-of-bounds hunks are stripped per `context.yaml`. | `proven` | **unit** — same file, the `allowed_paths` strip cases. Tier diagnostic below. |
| C10 | Isolation is enabled by an **opt-in** US-9 policy (`SandboxSettings`), resolved at the composition root. | `proven` | e2e — `test_policy_enforced_runs_bash_bounded_to_worktree` drives the policy rather than a per-step flag; composition-root resolution at unit (`test_settings_loader.py`, `test_isolation_gate.py`). |
| C11 | Default-off preserves today's behaviour **exactly**. | `proven` | e2e — the paired controls `test_run_tests_not_isolated_runs_at_project_root` and `test_not_isolated_runs_bash_at_project_root`: `.worktrees` absent from stdout and the write lands at the real root. *Exactly* is a universal; the controls establish the observable half. |

### Finding: the contract asserts three things are rebound, and one is

`C6` is the plan's predicted two-halves case, and probing it produced a **different** answer than
expected. The claim reads *"the `SubprocessExecutor` security boundary — credential stripping,
resource limits, `cwd` containment — is rebound to the worktree path."*

Only `cwd` is path-dependent. The first attempt at a seam test asserted that a credential set in the
parent does not reach the isolated child — and the probe showed **the same script run un-isolated
also reports it absent**, because stripping applies on every path. The assertion could not fail for
the reason it claimed, and would have passed with isolation removed entirely. It is the third
vacuous assertion this audit has caught in its own work, and the first caught before commit.

So `C6` is `unprovable` **as written**, not unproven: `cwd` containment is proven, and the other two
protections are not the kind of thing that can be rebound. The guard that the allow-list survives
the rebind is kept in the new test, labelled as a regression guard rather than cited as proof.

### FR-6 — capability findings

`C8` and `C9` (Main-Branch-Wins strip-merge; out-of-bounds hunks stripped per `context.yaml`) are
seam claims proven **only at unit tier**, in `D-EXEC-02`'s own `test_git_atom.py`. That is the
`ADR-003` diagnostic: the reconcile seam has no integration-tier proof of its own, and the finding
belongs to `D-EXEC-02`, not to this contract. Recorded here; `SF-03` consolidates.

## `INT-US-21` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/workflows/test_feature_decomposition_e2e.py` | e2e | 24 |
| `tests/integration/core/flow/handlers/test_decomposition_artifacts_integration.py` | integration | 33 |
| `tests/integration/core/flow/engine/test_seam_pins.py` | integration | 4 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `sw run feature_decomposition` is a working three-session journey: draft (exists-skip) -> park -> resume-as-approval -> validate -> decompose -> park -> resume -> COMPLETED. | `proven` | e2e — `TestE1HappyJourney::test_the_journey_completes_across_three_sessions` drives the REAL CLI and asserts `PARKED` at **both** gates before `COMPLETED`, reading persisted run status rather than exit code. `TestE11ResumeAnUnparkedRun::test_a_parked_run_is_still_resumable`. |
| C2 | It produces a durable uuid-tagged `<stem>_decomposition.yaml`. | `proven` | integration — `TestPersistenceSeams::test_lineage_row_written_to_real_sqlite_with_the_artifact_uuid` extracts the uuid **from the artifact's own text** and matches it to the lineage row; `TestArtifactBoundaries::test_rerun_reuses_the_artifact_uuid_across_two_real_runs` proves durability across runs. e2e: `test_the_artifact_and_stubs_reach_disk`. |
| C3 | It produces one never-overwritten stub component spec per DAG node. | `proven` | integration — `TestStubComponentSpecs::test_one_stub_written_per_component_next_to_the_spec` + `::test_existing_spec_is_never_overwritten`; e2e `TestE7StubNoOverwrite::test_a_hand_authored_component_spec_is_untouched`. |
| C4 | The journey costs **exactly one** LLM call. | `proven` | e2e — `TestE1HappyJourney::test_the_decomposition_costs_exactly_one_llm_call` asserts `llm.calls == 1` across all three sessions. |
| C5 | Handlers are registered, so the bundled pipeline can execute a step at all. | `proven` | integration — `TestArtifactThroughTheRealRunner::test_registry_resolved_run_writes_the_artifact_next_to_the_spec`. **Extracted by CB-3, not CB-1 — see below.** |
| C6 | `context.plan` is populated by the runner hook, not documented-but-unwritten. | `proven` | integration — `TestPlanBridgeIsHookDriven::test_plan_reaches_the_next_step_without_being_seeded`, and `::test_the_hook_is_what_sets_it` **deletes the artifact between steps** to prove causation rather than correlation. **Extracted by CB-3.** |
| C7 | The flow engine has HITL approval semantics — `sw resume` advances rather than re-parking forever. | `proven` | e2e — the two `_resume` advances inside `test_the_journey_completes_across_three_sessions`; `TestE11ResumeAnUnparkedRun::test_resuming_a_finished_run_is_refused`. **Extracted by CB-3.** |
| C8 | The plan artifact is persisted, where previously it never was. | `proven` | integration — `TestPersistenceSeams::test_output_survives_the_state_store_round_trip`, `::test_resume_rehydrates_decomposition_matching_the_artifact`. **Extracted by CB-3.** |

### Finding: the surprise was in CB-1's extraction, not in the tests

The plan predicted `INT-US-21` would be the cleaner entry and said *"a surprise here is worth more
attention than a gap in `INT-US-28`."* It was cleaner — **all 61 cited tests pass, none skips**, and
the suite is the strongest in the tree. `test_seam_pins.py` explicitly guards against
*"the capture handler proving itself (vacuous-proof pattern 2)"*, and `test_the_hook_is_what_sets_it`
deletes the artifact between steps so a stale value cannot pass for a live one. That is the standard
this audit has been measuring everything else against.

The defect was upstream. CB-1 extracted **four** claims from the Integration Description's first
sentence and stopped. The paragraph continues:

> *"It solves the built-but-not-integrated problem: `D-INTL-02` and `D-INTL-03` shipped capabilities
> behind a pipeline that could not execute a single step (unregistered handlers), a `context.plan`
> documented as hook-populated with **zero writes in `src/`**, a flow engine with no HITL approval
> semantics (`sw resume` re-parked forever, proven empirically), and a plan artifact that was never
> persisted. **All four are closed.**"*

*"All four are closed"* is four falsifiable assertions about the delivered system, and they are the
**reason the story existed**. They were not in the matrix. Added above as C5–C8; all four are
proven, so nothing was broken — but a clean verdict had been about to be issued over an incomplete
list, which is the same failure shape as a green ledger over an unread test.

**Consequence for the remaining entries.** CB-1's rule was one claim per assertion at a seam; in
practice it read the first sentence of each Integration Description. The other 11 entries were
extracted the same way and should be re-read against their full contract text during SF-02/SF-03,
not merely verdicted. `INT-US-28`'s six claims were checked against its contract during CB-3 and are
complete.

**Benign drift, recorded not repaired (NFR-1).** The contract's Verifiable Proof says *"22
scenarios"*; the file now holds 24 — the interrupt-teardown pair was added after the contract was
written. More proof than claimed, so nothing is over-stated; the count is simply stale.

## `INT-US-21-SUB` — Recursive Planning

**No test file cited.** Frozen in `scripts/baselines/proof_tier.json` with a named owner.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `C-INTL-01` implements iterative decomposition, resolving the AST graph into sub-tasks. **(Out of SF-01 scope — `TECH-018`/`TECH-038` already established this claim is false; recorded for completeness.)** | `unassessed` | — |

## `INT-US-24` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py` | e2e | 9 |
| `tests/integration/workflows/scenarios/test_converter_execution.py` | integration | 4 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `sw run scenario_integration <spec>` is a real working journey through the QA Runner on the shipped US-3 loop. | `unassessed` | — |
| C2 | A green verification round costs **zero** arbitration LLM calls. | `unassessed` | — |
| C3 | A parked `spec_ambiguity` heals through the loop on `sw resume`, with evidence re-published on the fresh round. | `unassessed` | — |
| C4 | The declared stage chain is what runs: contract extraction → parallel coding + scenario pipelines → JOIN → scenario test execution → **arbiter fault attribution** (`B-FLOW-01`). | `unassessed` | — |
| C5 | The journey executes through the QA Runner (`D-VAL-01`) **on top of the shipped US-3 loop** (`INT-US-03`). | `unassessed` | — |
| C6 | **Exclusion:** DAL escalation for run journeys is deliberately delegated to `C-EXEC-07` / `INT-US-09-SF06` and is NOT covered here. | `unassessed` | — |

## `INT-US-25` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/workspace/test_constitution_e2e.py` | e2e | 15 |
| `tests/integration/interfaces/cli/test_cli_constitution.py` | integration | 8 |
| `tests/integration/interfaces/cli/test_profile_check_seam.py` | integration | 6 |
| `tests/e2e/capabilities/workspace/test_domain_profile_e2e.py` | e2e | 10 |
| `tests/e2e/capabilities/workflows/test_dal_e2e_pipeline.py` | e2e | 5 |
| `tests/e2e/capabilities/assurance/test_validation_dal_enforcement.py` | e2e | 2 |
| `tests/e2e/capabilities/assurance/test_validation_pipeline_e2e.py` | e2e | 11 |
| `tests/e2e/capabilities/assurance/test_standards_e2e.py` | e2e | 5 |
| `tests/integration/interfaces/cli/test_cli_standards_integration.py` | integration | 13 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `CONSTITUTION.md` is resolved by walk-up. | `unassessed` | — |
| C2 | It is size-capped via `sw config set-constitution-max-size`. | `unassessed` | — |
| C3 | It is injected into the prompt of `review spec`, `review code` and `implement`. | `unassessed` | — |
| C4 | Absence of the file means no injection, not a broken prompt. | `unassessed` | — |
| C5 | A project-local file overrides the default. | `unassessed` | — |
| C6 | `sw config set-profile` makes `sw check --level component` load that profile's pipeline YAML. | `unassessed` | — |
| C7 | `--pipeline` and `--level feature` both override the active profile. | `unassessed` | — |
| C8 | A nested `operational.dal_level` makes a warn-only spec FAIL under `DAL_A` and pass under `DAL_E`. | `unassessed` | — |
| C9 | The standards scan upserts rather than duplicates, and honours `.specweaverignore`. | `unassessed` | — |
| C10 | `sw constitution init/show/check` manages a project-wide `CONSTITUTION.md` (`C-VAL-01`) — the CLI surface itself, including oversize rejection and refuse-to-overwrite. | `unassessed` | — |
| C11 | `sw config set-profile <name>` selects one of **five** preset bundles. | `unassessed` | — |
| C12 | Each profile pipeline carries `extends: validation_spec_default`, so `D-VAL-02`'s YAML inheritance resolves as part of the same round trip. | `unassessed` | — |
| C13 | **Exclusion:** the code-level half of `C-VAL-03` — a strict DAL changing the verdict on LLM-**generated** code — is delegated to `TECH-041` and is NOT covered by this contract. | `unassessed` | — |

## `INT-US-28` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/integration/workspace/test_memory_integration.py` | integration | 26 |
| `tests/integration/workspace/test_memory_hydration_flow.py` | integration | 1 |
| `tests/integration/core/flow/handlers/test_prompt_hydration.py` | integration | 2 |
| `tests/integration/core/flow/engine/test_handover_persistence.py` | integration | 3 |
| `tests/unit/workspace/test_memory_hydrator.py` | unit | 15 |
| `tests/unit/workspace/test_bootstrap_protocol.py` | unit | 5 |
| `tests/unit/core/flow/engine/test_handover.py` | unit | 20 |
| `tests/unit/core/flow/engine/test_runner_handover.py` | unit | 7 |
| `tests/unit/core/flow/handlers/test_build_base_prompt.py` | unit | 9 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `B-INTL-09` provides a persistent SQLite schema with CRUD, a formal state machine, OCC concurrency, circuit breakers, zombie recovery and upstream DAG propagation. | `proven` | integration — `test_int_1_orchestrator_happy_path` (schema+CRUD), `test_int_9_occ_concurrent_race` (OCC), `test_int_6_circuit_breaker` + `test_int_12_circuit_breaker_three_strikes`, `test_int_2_zombie_reaper` + `test_int_11_zombie_reaper_full_cycle`, `test_int_17_upstream_propagation_cascade` + `test_int_20_diamond_dependency_propagation`. All in `test_memory_integration.py`. |
| C2 | `D-INTL-06` provides read-side retrieval, trust-tagged XML formatting with 8KB payload limits, and fail-safe handover (save on completion, bootstrap on hydration). | `proven` | **unit** — `test_hydrate_standard`, `test_format_prompt_block_standard`, `test_bootstrap_trust_tagging`, `test_handover_under_8kb`, `test_bootstrap_hydrates_existing_handover`. Integration only for the read side (`test_memory_hydration_integration_flow`). |
| C3 | **Seam:** the `handover_context` JSON column on `Task` is the shared surface — `B-INTL-09` owns write-side validation (Pydantic schema, 8KB limit, truncation on ARCHIVED), `D-INTL-06` owns read-side. | `proven` | integration — `test_memory_hydration_integration_flow`, *"end-to-end compatibility between the Write-Side (MemoryRepository) and the Read-Side (MemoryHydrator)"*, plus `test_build_base_prompt_with_corrupted_handover` for the invalid-payload path. **Partial:** the 8KB cap and ARCHIVED truncation are proven only in the provider's own unit tests (`B-INTL-09` NFR-6, FR-7), never across the seam. |
| C4 | **Seam:** `_build_base_prompt()` calls `MemoryHydrator` to inject memory context into **every** LLM prompt. | `proven` | integration — `test_build_base_prompt_with_hydration` proves the injection. The **"every"** was unproven and is now `test_no_prompt_is_built_outside_build_base_prompt` (written at this boundary): `PromptBuilder` is constructed nowhere outside its own module and `_build_base_prompt`. |
| C5 | **Seam:** `save_handover_context()` persists pipeline telemetry in the runner's `finally` block. | `proven` | integration — `test_runner_finally_persists_handover_end_to_end` **and** `test_runner_resume_finally_persists_handover_end_to_end`, both written at this boundary. The runner persists from **two** entry points (`run()` and `resume()`); each now has a mock-free span. Was `unproven`: see the finding below. |
| C6 | **Boundary:** `core.flow` consumes `workspace.memory` via `core/flow/context.yaml`, clean under `tach check`. | `proven` | unit — `test_tach_architectural_boundaries` shells out to `tach check`. Correct instrument: this is an `[proof: arch]` claim, provable by the boundary tool and not by a pytest assertion about behaviour. |

### Finding: C5 was proven in two halves that met at a mock

The strongest result of CB-2, and it took a probe rather than a reading to establish.

`INT-US-28` claims *"`save_handover_context()` … persists pipeline telemetry to the Memory Bank in
the runner's `finally` block."* The description is accurate — `runner.py:175` and `:229` both call
`_save_handover` from a `finally:`. Two sets of tests appeared to cover it:

* `tests/unit/core/flow/engine/test_runner_handover.py` drives a **real** `PipelineRunner` and
  asserts the `finally` fires on success, failure, park and empty pipeline — with
  `runner._save_handover = AsyncMock()`, so nothing reaches a database;
* `tests/integration/core/flow/engine/test_handover_persistence.py` writes to a **real** database —
  by calling `save_handover_context(ctx, run)` directly, so the runner is never involved.

Each half passes while the wiring between them is broken. **Probed:** severing `_save_handover` with
an early `return` leaves all three pre-existing integration tests green.
`test_runner_finally_persists_handover_end_to_end` was written here — real runner, real registered
step, real SQLite, no mock between them — and fails on that same break with *"the runner's finally
never reached the DB"*.

**Both entry points, not one.** `runner.py` saves handover from `run()` (line 176) and from
`resume()` (line 229). The first span test covered only `run()`, leaving `resume()` in exactly the
shape this finding is about — `test_runner_resume_calls_save_handover` drives a real runner with
`_save_handover` mocked, and the direct-call tests never touch a runner.
`test_runner_resume_finally_persists_handover_end_to_end` closes it: it runs, **clears the handover
column**, resumes, and asserts a row reappears — so a pass can only mean the *resumed* run wrote it.
Probed by severing `resume()`'s `finally` alone, which fails that test and no other.

**Duplication removed while here.** Both `finally` blocks repeated `_save_handover` +
`_flush_telemetry`, so a change to one could silently miss the other. Extracted to `_finalize()`;
severing handover inside it now fails **both** seam tests from a single point. Outside this ticket's
audit-only scope, done because the path was already open and the change is six lines covered by
existing tests — recorded here rather than filed.

### Finding: the C4 guard was itself vacuous on the first attempt

Written to make *"every LLM prompt"* falsifiable, the guard resolved its repo root with
`parents[4]` — which lands on `tests/`, not the repository. It globbed a directory that does not
exist, found no offenders, and **passed with a deliberate bypass planted in `decompose.py`**. Fixed
to `parents[5]` and given an explicit assertion that the source tree was found at all, per
`TECH-032`: a check that cannot find its subject must say so, not pass. It now fails on the planted
bypass and passes clean.

Worth recording because it is this audit's own thesis landing on the auditor twice in one sitting —
first the `failed == 1` grep that reported a control missing when it existed, now a guard that
proved nothing while reporting success.

### Finding: 5 of the 9 cited files are capability tests, not seam tests (`FR-6`)

Raised 2026-08-13 when the tier column read `integration, unit` — the only entry in the matrix with
a `unit` tier, which the plan's own guidance calls a **diagnostic** rather than a style choice.

`git log` settles what happened. **4 of the 5 unit files were created 2026-05-10, the day
`INT-US-28` was delivered** (`test_bootstrap_protocol.py` 5, `test_handover.py` 20,
`test_runner_handover.py` 7, `test_build_base_prompt.py` 9); only `test_memory_hydrator.py` (15)
predates it. So **41 of the 56 unit tests were written during the integration story** — the story
did not merely cite existing unit tests, it wrote them.

They are real tests and they pass. What was wrong was the **attribution**: they prove `B-INTL-09`
and `D-INTL-06`'s own requirements (hydrator sanitisation and truncation, handover save fail-safes,
`_build_base_prompt` assembly), and were credited only to the contract that consumed them. Both
capabilities therefore read as having **9 FRs and zero cited tests** — `check_fr_coverage.py`
reported both `BLOCKED` — while the contract read as proven by 88 tests when its seam has 6.

**Handled, not filed.** Each file was read against each FR and given a `Proves:` citation for the
requirements it actually demonstrates — `B-INTL-09` FR-2/3/4/5/8/9 (from the *integration* file,
which is where that capability's proof genuinely lives) and `D-INTL-06` FR-4/5/6/8/9. The remaining
seven (`B-INTL-09` FR-1/6/7, `D-INTL-06` FR-1/2/3/7) are **left uncited on purpose**: no test here
proves them, and citing them to green a ledger is the gaming the sweep's failure message forbids.
`check_fr_sweep` fell **251 → 240** as a result (11 requirements honestly cited), and the baseline
was tightened to match.

**A trap worth recording, because this audit walked into it.** The first attempt put the citations
in the *first* `"""` of each file — which in all five was a fixture's or function's docstring, not
the module's, because none of these files had a module docstring. The second put a disclaimer in the
test naming the requirements deliberately left uncited. `check_fr_coverage.py` credits **any**
`FR-N` mentioned in a file that names the story, so that disclaimer silently marked all three
covered and the sweep read 237 instead of 240 — a *better* number produced by writing down that
something was untested. Both are fixed; the uncited requirements are named in the capability
designs, never in the tests.

The gate was then checked rather than blamed: across all 18 delivered stories that cite anything,
**102 of 104 declared-FR credits carry a deliberate attribution** (`Proves:`, `[Boundary/FR-5]`,
`(FR-2 producer)`), and the two exceptions are attributions this sweep's own regex failed to
recognise, not false credits. So the ledger is sound and no gate change is warranted — the hazard is
narrow: **a file that *discusses* a story's requirements is credited as proving them.**

This changes no verdict below and re-words nothing in `US-28_integration.md` (`NFR-1`). It is
recorded here because C1 and C2 are claims **about the capabilities**, and CB-2 must not credit
their seam with proof that belongs upstream of it.
