# LLM settings — decisions from the C-FLOW-13 grilling (2026-09-26)

Every decision below was put to the user and answered by the user, mostly by delegating to the
recommendation ("your recommendations for all"). Each names the feature that owns it
`[agreed 2026-09-26]`. Facts behind the questions: the settings inventory and the subject-scatter audit
(K1), and the Phase 2 research briefs.

## Owned by C-FLOW-13 — the central settings

| # | Decision |
|---|---|
| Q0 | `C-FLOW-13` is widened to own the one central place for every LLM setting |
| Q1 | In scope: API key *names*, provider and model per role, sampling, prices, limit values, server addresses, routing |
| Q2 | API keys stay in environment variables; settings only name the variable |
| Q3 | Edited through `sw` commands and a readable text file |
| Q4 | Levels: machine-global defaults + per-project override; per-run override for the model only |
| Q5 | The project level is committed with the project; prices and keys stay machine-level |
| Q7 | Machine level is a file: `~/.specweaver/settings.toml` (under `SPECWEAVER_DATA_DIR` when set) |
| Q8 | Project level is an `[llm]` section in the project's `specweaver.toml` |
| Q9 | Today's DB settings (`llm_profiles`, `llm_project_links`, `llm_cost_overrides`) are moved into the files once; the tables are removed in a later release, announced |
| Q12 | A broken settings file refuses to run, naming file and line; a missing file means built-in defaults |
| Q14 | Each server entry has a maximum of parallel requests |
| Q16 | Each model's catalogue entry carries its own defaults (context size, max output, sampling); role and project settings override them |
| Q18 | Each server entry states whether data leaves the machine; a project may require "private only" — no silent fallback to the cloud |
| Q22 | Money in CHF; the USD→CHF rate is a manual, dated value in the machine file; never fetched |
| Q35 | A project file cannot set server addresses or key names — it only chooses among what the machine file registers |
| Q43 | `D-FLOW-05` (Model Catalogue Adoption) is folded into `C-FLOW-13`; its ID is retired |
| Q44 | The file shape: `[servers.<name>]` (kind, base_url, api_key_env, private, max_parallel), `[roles]` as `model@server`, `[brake]` values, `[models."<id>"]` for facts the catalogue lacks, `[currency]`; the project `[llm]` may set `private_only` and `[llm.roles]` only |
| Q37 | The catalogue is seeded from models.dev (MIT, credited), shipped with its version stamped, never fetched at runtime; updating it is a deliberate, reviewable command |
| — | The brake *values* live here: check-in intervals CHF 20 (hosted) and 2 h GPU time (local) per run, parallel 3 hosted / 4 GB10, 10 agent turns — all marked unverified until the user has seen real costs (Q11) |

## Owned by B-FLOW-05 — how the brake behaves

| # | Decision |
|---|---|
| Q13 | Two totals per run, never added together: CHF for hosted models, GPU time for local ones |
| Q10 | A hosted model with no known price is refused while a money check-in is on; local models are measured in GPU time |
| Q33 | The budget is an emergency brake, not a price estimate: one check-in per run, covering the whole call tree |
| Q21 | At a check-in the run pauses and asks; it never downgrades or switches models |
| Q34 | No monthly limit in SpecWeaver; providers' billing limits do that; `sw costs` shows month-to-date |
| Q36 | With nobody to answer (nightly, CI) a check-in stops and parks the run, resumable with `sw resume` |
| Q38 | The per-run token limit is dropped; tokens are recorded, not used as a brake |
| Q39 | Calls already running may overshoot a check-in; the pause message says by how much |
| Q40 | Before each call its worst case (input × price + max output × price) is checked; crossing it pauses first |
| Q41 | Every call carries a hard output cap that includes thinking tokens; a model that cannot be capped is refused while a money check-in is on |

## Owned by A-FLOW-01 — measuring and choosing (planned directly after C-FLOW-13)

| # | Decision |
|---|---|
| Q17, Q19 | Duration recorded per call and summed per task (a step incl. retries and turns) and per run |
| Q20 | Each call records whether its step passed its own gate |
| Q37 note | Models are compared by measured cost *per task*, never by price per token |
| Q23–Q28 | "Good enough, cheapest" selection: a bar per task type (strict 95% / relaxed 80%), a confidence-bound verdict (min 10 tasks), evidence shared across projects, cheapest-first exploration, escalation after 2 failures within the brake — **moved here, still to be designed** |

**Open conflict for A-FLOW-01's design:** its registry entry says it *suggests and never auto-applies*;
Q24 (escalate automatically after 2 failures) and Q28 (cheapest-first exploration) apply choices
automatically. Which one holds is the user's call when A-FLOW-01 is designed.

## Dropped for now

Q29 layers 2–3 and Q30–Q32 (blame across chains and manager/worker roles): the multi-agent setup
(`C-FLOW-11`, `B-INTL-06`) does not run yet.

## Research facts that shaped the answers

- Routed calls in `sw run` bypass the spend brake, the rate limit and the usage flush
  (`router.py:120`, `collector.py:60`, `engine/telemetry.py:21-23`).
- No surveyed tool pauses and asks at a budget; all stop hard. The non-interactive behaviour is ours
  to define (Q36).
- Codex CLI refuses project-level `base_url` for the same reason as Q35.
- Qwen3-Coder-Next on vLLM: prefer `--tool-call-parser qwen3_xml`; `qwen3_coder` loops on long
  inputs with tools.
