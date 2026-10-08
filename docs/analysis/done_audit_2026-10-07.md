# Audit of "done" — 2026-10-07

Asked by the user after B-FLOW-05 and C-FLOW-13 were reported done: are they, corner cases
included, and what else was signed off without being done properly. Four read-only agents; the
critical findings were re-run by hand. Repro scripts are in `.tmp/` (gitignored):
`cflow13/`, `repro_*.py`, `dval05/`, `eflow01/`, `sens/`, `arch/`.

## Verdict

- **B-FLOW-05 is not done.** 18 corner cases (2 critical, 4 high).
- **C-FLOW-13 is not done.** 23 corner cases, 1 critical: a private-only project's code reached a
  hosted server (re-run by hand, verified).
- **Of 141 items marked done across the project, 26 are false** (a promised behaviour is missing
  or broken) and 73 weak; 42 hold. Only one ✅ capability (B-SENS-03) has a mutation campaign.

## B-FLOW-05 — Spend Brake

| # | Sev | Finding | Evidence |
|---|---|---|---|
| 1 | CRIT | `sw drift check --analyze` prints "✓ AST signatures match" and exits 0 when the brake stops the root-cause call — exactly on drifted files | `cli_drift.py:104,116`; `step_execution.py:219-236`; `.tmp/repro_drift.py`. **Fixed** 2026-10-07: a parked step keeps its findings; the command names the limit and exits 42 |
| 2 | CRIT | A brake park inside session isolation raises `RuntimeError` (misleading "HITL" message); `sw implement` enables it automatically on high-DAL projects; code torn down | `session.py:81`; `implementation/interfaces/cli.py:281`. **Fixed** 2026-10-08 (user chose: keep the worktree): a parked run keeps its worktree and resumes in it; `sw implement` (no resume) ends cleanly |
| 3 | HIGH | Per-step worktree isolation skips the park check: run FAILED, retried, partial work merged | `step_execution.py:202-207`; `.tmp/repro_sandbox.py`. **Fixed** 2026-10-07: the step parks and nothing is merged |
| 4 | HIGH | Gemini thinking tokens (`thoughts_token_count`) never counted | `adapters/gemini.py:178,249` |
| 5 | HIGH | Ctrl-C mid-step: run left RUNNING, spend saved as at step start; resume pays the step again unasked | `runner.py:172-176,317-325` |
| 6 | HIGH | Fan-out / dual pipeline: one sub-run's stop parks siblings and discards their paid results; resume re-runs all | `fan_out.py:61`; `dual_pipeline.py:42`; `.tmp/repro_fanout.py` |
| 7 | MED | `budget.stopped` never resets: `sw standards scan` drops every later scope silently | `budget.py`; `standards/interfaces/cli.py:97-157` |
| 8 | MED | After a "no", every further call asks again; a later "yes" spends, but the step is parked anyway | `budget.py:136-153`; `.tmp/repro_budget.py` |
| 9 | MED | A parked step re-runs from the start on resume, repeating paid calls | `approval.py` |
| 10 | MED | A response without `usage` counts as 0, so `tokens_per_run` never fills on such servers | `openai.py:160-164`; `.tmp/repro_no_usage.py` |
| 11 | MED | `--model` drops role limits (maybe intended — user's call) | `resolve.py:209-217` |
| 12 | MED | Queued calls hold reservations before the parallel limit; the question then reads "0 of X spent" with no visible reason; overshoot not shown (FR-6) | `collector.py:128`; `_rate_limit.py:51` |
| 13 | MED-LOW | Round 1+ checks leave out tool schemas (and Gemini's system instruction) | adapters' `before_request` |
| 14 | LOW-MED | `sw run --json \| jq`: the question goes into the NDJSON stream; the run hangs | `_core.py:131-141` |
| 15 | LOW | "Yes" on one limit then a stop on another leaves the first raised | `budget.py:138-153` |
| 16 | LOW | After resume, raised limits of keys not touched this session are dropped from the next snapshot | `budget.py:121-129` |
| 17 | LOW | The 80% warning is not re-armed after a raise; its message uses the base value | `budget.py:180-191` |
| 18 | LOW | Ctrl-D at the question: an error, not a stop; a retry gate repeats paid calls | `_core.ask_to_spend` |

Also: the same model on two servers shares one model limit (`resolve.py:183`) — user's call.

## C-FLOW-13 — central LLM settings

| # | Sev | Finding | Evidence |
|---|---|---|---|
| 1 | CRIT | `--project priv` while another project is active: settings come from the **active** project; a `private_only` project's spec went to a hosted server | `core/flow/interfaces/cli.py:250,276`; review/implementation CLIs; `.tmp/cflow13/test_repro_project_mismatch.py` (re-run 2026-10-07). **Fixed** 2026-10-07: commands read the target folder's settings |
| 2 | HIGH | Broken TOML or a BOM: `set-role` / `costs reset` end in a raw traceback | `llm_settings_writer.py:104-128` |
| 3 | HIGH | `set-role` on a `[roles.review]` table deletes comments and keys | `llm_settings_writer.py:105` |
| 4 | MED | Wrong line numbers for dotted keys and multi-line strings | `llm_settings.py:515-521` |
| 5 | MED | Resolver refusals say `settings.toml:0` | `resolve.py` |
| 6 | MED | `[models."openai/gpt-5"]` override silently ignored (only bare ids match) | `catalogue.py:67` |
| 7 | MED | `sw costs set <model>` prices the model on every kind, GB10 included | `catalogue.py:67` |
| 8 | MED | `kind = "openai"` with a custom `base_url` sends the real `OPENAI_API_KEY` to that host | `llm_settings.py:79`; `servers.py` |
| 9 | MED | A secret pasted into `api_key_env` is printed by `config show` and errors | `llm_settings.py:408` |
| 10 | MED | `schema_version = "2"`, `0`, `true` accepted | `llm_settings.py:221` |
| 11 | MED | Project file has no `schema_version` gate | `ProjectLlmSection` |
| 12 | MED | `config show` omits catalogue output limit and sampling actually used, and `default` fallbacks | `settings_report` |
| 13 | MED | Role `temperature` on openai/anthropic shown as in effect, never sent | adapters |
| 14 | MED | `--model` drops role limits (same as B-FLOW-05 #11) | `resolve.py` |
| 15 | MED | `sw standards scan`: a server typo or private-only violation prints a dim "No model used" and goes on | `command.py:72-74` |
| 16 | LOW-MED | `temperature = 50`, `top_p = -3` accepted; fail mid-run | `RoleEntry` |
| 17 | LOW | Unset-role refusal does not name `sw config set-role` (FR-11) | `resolve.py:214` |
| 18 | LOW | `sw costs` lacks the catalogue version stamp; spend merged across servers | infra `cli.py` |
| 19 | LOW | `sw usage` refused on a broken machine file | infra `cli.py:309` |
| 20 | LOW | Writer: CRLF→LF, mode 600→664, float noise, `inf` accepted, future `rate_date` accepted | writer |
| 21 | LOW | Parallel limit per (loop, name): stale after edits, two names on one address | `_rate_limit.py` (suspected) |
| 22 | LOW | Catalogue drops tiered/reasoning/cache prices | `update_model_catalogue.py` (suspected) |
| 23 | Info | `max_output_tokens = 4096`, `AutonomySettings.max_turns = 10` still in code (dead) | `models.py:73`; `settings.py:118` |

## User paths (US-16 P1–P8, US-04 S1–S7)

Proven end to end: P2, P3, P8, S4, S5 (and S3's price half). Partial: P1, P4, P6, P7, S1, S2,
S3, S6, S7 — each has at least one step proven only below e2e or through a stand-in (details in
the agent report: S7 never runs the real drift handler; S2's resume is integration-only; S6 is
proven through `/review`, not `/implement`).

## Census of signed-off work

141 items: 63 ✅ capabilities, 13 🟢 INT-US stories, 65 🟢 TECH tickets.

| Class | Caps | INT | TECH | Total |
|---|---|---|---|---|
| A holds | 9 | 2 | 31 | 42 |
| B weak | 31 | 10 | 32 | 73 |
| C false | 23 | 1 | 2 | 26 |

**False (C)** — a promised behaviour missing or broken:

| ID | Broken | Evidence |
|---|---|---|
| D-EXEC-02, INT-US-09 FR-5 | Per-step worktree isolation discards all output (no commit before strip-merge, empty allow-list); run says COMPLETED. **Fixed** 2026-10-08 (user chose the session rule): commit, then merge only a passed step's targets; FR-7 micro-sync withdrawn | `sandboxed_execution.py:96-112` |
| E-SENS-01 | grep/find follow symlinks out of the root. **Fixed** 2026-10-08: the search path is contained, symlinks are skipped | `sandbox/filesystem/interfaces/tool.py:189-234`; `core/search.py:223` |
| E-SENS-02 | `web_search` dead: WebTool built with no key | `sandbox/registry.py:87` |
| E-SENS-03 | Workspace boundaries never set: reviewer and planner get full access | `run_context.py:114-123`; `security.py:128` |
| E-INTL-01 FR-3 | No secret redaction before prompts | only MCP `scrub_secrets` exists |
| E-INTL-03 | Review verdict parsing: DENIED text mentioning "VERDICT: ACCEPTED" parses ACCEPTED. **Fixed** 2026-10-08: the first verdict line decides | `reviewer.py:224-227` |
| B-INTL-01 FR-1/4 | Archetype spec pipeline never loaded; S12 list params crash | `handlers/validation.py:228` |
| B-INTL-09 FR-6, D-INTL-06 | Foreign keys off in production sessions; nothing creates memory tasks | `register_fk_pragma_listener` test-only |
| C-FLOW-06 FR-1/2 | `stale_nodes` never written; skeletons dropped | `run_context.py:114` |
| B-FLOW-01 FR-1/9/10 | S07 warns not rejects; no stack trace to the coder; ambiguity park not resumable | `s07_test_first.py:122`; `arbiter.py` |
| C-EXEC-02 FR-2/12/13 | Load-time containment/PATH checks missing; atom raises on `env:null`; crashes FAILED not ERROR | `models.py:380`; `atom.py:128` |
| C-EXEC-06 FR-4/5 | Reconcile failure leaves COMPLETED; glob allow-lists exact-match | `runner.py:276`; `worktree_ops.py:128` |
| E-EXEC-01 FR-2/4 | No per-DAL timeouts; no peak memory | `executor.py` |
| E-INTL-02 FR-2 | Draft accept/modify/reject step missing | `drafting/_base.py:136-200` |
| D-SENS-03 FR-4/5 | Markdown/SQL traceability always empty | `markdown/codestructure.py:70` |
| D-VAL-05 | C04 never yields coverage; relative paths break C02/C04/C05 | `validation_hydrator.py:257` |
| D-INTL-03 | No shipped pipeline, CLI or API has a plan step | `new_feature.yaml` |
| D-FLOW-04 FR-6 | Logger rollout incomplete (107 of 360 modules) | grep |
| D-FLOW-03, E-FLOW-03 | Superseded by C-FLOW-13; designs still say COMPLETE | removed tables/commands |
| D-SENS-02 FR-3, TECH-003 FR-3 | Stale `loom/` layout consumed by 3 `context.yaml` | workspace `context.yaml` |
| C-VAL-02 | "Produces bulk-written overrides" is false | `core/config/profiles.py:7` |
| TECH-004 FR-6 | `resolve_service_name` unused and always "default" | `assurance/graph/loader.py:62` |
| C-FLOW-01 (REST) | `POST /review`, `/implement` crashed on every call until `67f51443`; now works, still weakly tested | `test_telemetry_wiring.py` mocks |

**Baselines hiding debt:** `fr_uncited.json` (127 FRs, undercounts by ≥ 20 — the sweep only scans
some roadmap lines and skips unparsable FR tables); `nfr_uncited.json` (120 behavioural NFRs, most
security/isolation); `delivered_claims.json` frozen at 22 while live is 15 (7 regressions would
pass); `check_story_preconditions.py` passes stories whose FR ledgers are blocked.

## What happens next

The user decides: which statuses to reopen, and the order of fixes. Recommendation recorded in the
reply of 2026-10-07: security and silent-wrong-result findings first.
