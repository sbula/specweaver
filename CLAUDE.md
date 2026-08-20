# SpecWeaver

> Specification-driven development lifecycle tool. Enforces spec quality through a 12-test battery and manages AI agents via role-restricted tool interfaces.

## Tech Stack

- **Language:** Python 3.11+ (strict mypy, ruff lint)
- **Package Manager:** uv (NOT pip)
- **Test Runner:** pytest (markers: `live`, `integration`, `e2e`)
- **Boundary Enforcement:** tach (module dependency boundaries in `tach.toml`)
- **Architecture:** DDD + Hexagonal. Pure domain logic; I/O at the edges via adapters.

## Project Map

```
src/specweaver/
├── core/               # Domain kernel
│   ├── config/         # Pydantic settings + SQLite DB
│   └── flow/           # Pipeline engine (models, runners, gates, handlers)
├── graph/              # In-Memory Knowledge Graph (NetworkX)
│   ├── lineage/        # Change lineage tracking
│   └── interfaces/     # CLI bindings for graph commands
├── sandbox/            # Execution engine (3-layer)
│   ├── tools/          # Agent-facing capability providers
│   ├── atoms/          # Engine-internal workflow ops
│   └── commons/        # Shared executors + helpers
├── infrastructure/     # External adapters
│   └── llm/            # LLM provider abstraction + adapters
├── interfaces/         # Delivery mechanisms
│   ├── cli/            # Typer CLI (`sw` command)
│   └── api/            # FastAPI REST server
├── workflows/          # Business processes
│   ├── drafting/       # LLM-assisted spec drafting
│   ├── implementation/ # Code generation from specs
│   ├── planning/       # Implementation plan generation
│   └── review/         # LLM-based spec/code review
├── workspace/          # Project discovery, AST, analyzers
├── assurance/          # Quality enforcement
│   ├── validation/     # 12-test spec quality battery
│   └── standards/      # Codebase standards auto-discovery
└── commons/            # Cross-cutting shared utilities

specs/                  # YAML spec definitions (input to validation battery)
```

## Test Commands

> [!IMPORTANT]
> **Use `.venv/Scripts/python.exe` (Windows) / `.venv/bin/python` (Linux), not a bare `python`.**
> The system interpreter can import `specweaver` and will happily run the suite, but it does
> **not** have `pytest-xdist` installed — so `-n auto` is silently unavailable there and every
> run is serial. This is not theoretical: a full suite was run four times at ~13 min each before
> anyone noticed it could be 4.5.
>
> **Add `-n auto` for anything tier-sized or larger; leave single modules serial.** Measured on a
> 16-core box: one module 12.5s serial vs 15.2s parallel (worker startup loses); `tests/unit`
> 5m02 serial vs 1m37 parallel (3.1x); full suite ~13m vs 4m26 (2.9x). The crossover sits
> between one module and one tier. **The parallel full-suite figure is now ~1m15** (measured
> 2026-08-18, three runs); the serial numbers have not been re-measured since, so the ratios
> above are the 2026-08-16 evidence and the conclusion, not the current arithmetic.
>
> `scripts/tests.py` already passes `-n auto` itself — prefer it at commit boundaries and you
> get this for free.

```bash
PY=.venv/Scripts/python.exe   # Linux: .venv/bin/python

# Module-scoped (preferred — fast feedback). Serial on purpose: xdist startup costs more
# than it saves at this size.
$PY -m pytest tests/unit/core/ -v --tb=short
$PY -m pytest tests/unit/sandbox/ -v --tb=short
$PY -m pytest tests/unit/graph/ -v --tb=short

# By tier — always parallel
$PY -m pytest tests/unit/ -n auto --tb=short -q
$PY -m pytest tests/integration/ -n auto --tb=short -q
$PY -m pytest tests/e2e/ -n auto --tb=short -q

# Full suite (before commit) — always parallel
$PY -m pytest -n auto --tb=short -q

# Quality checks — one command, and it decides which checks run at which gate
$PY scripts/quality.py quick     # sub-second, diff-scoped
$PY scripts/quality.py cb        # commit boundary
$PY scripts/quality.py doc       # registries: roadmap, skills, FR/NFR ledgers
$PY scripts/quality.py matrix    # what runs where

# Mutation corpus — do the tests notice when behaviour disappears?
$PY scripts/mutation.py --gate   # morning: CLEAR, or the findings nobody has read
$PY scripts/mutation.py --confirm "<id>" --as will-fix --why "..."
$PY scripts/mutation.py --install-timer   # nightly at 03:00
```

> The mutation corpus is **not** part of any commit gate — it runs nightly and is judged by
> `--gate` in the morning. Writing a campaign, the four dispositions and the routine:
> `docs/dev_guides/writing_mutation_campaigns.md`.

> [!IMPORTANT]
> **The suite is green on Linux as of 2026-08-20: `8111 passed, 11 skipped` in ~1m27 (`-n auto`).**
> (Historic: `7511 passed, 11 skipped, 1 xfailed` in ~1m15 on 2026-08-18,
> measured over three consecutive runs.** The one `xfail` is strict and names its blocker — see `check_xfail_blockers.py`.
> **There are no accepted deltas.** A failure you see is a failure you caused — do not go looking
> for a "known Linux failure" list to file it under.
>
> This block previously recorded 25 chronic failures. All 25 are fixed; the root-cause analysis
> that closed them is kept at `docs/analysis/linux_test_failures_2026-08-12.md`. 18 were one
> production defect (`max_processes=128` becoming `setrlimit(RLIMIT_NPROC)`, which is per-real-UID
> and so bounded the *user* rather than the sandbox) — closed by **`TECH-029`**.
>
> **`TECH-029`'s `current task count + budget` backstop was itself replaced on 2026-08-18.** That
> ceiling sat *below* ordinary load — the UID's task count swings 313..960 during one `-n auto` run
> against a ~453 ceiling — so sandboxed bash steps died on their own `fork` about one run in six and
> the failure was reported against the innocent script. The headroom is now the budget **or 1% of the
> system's own hard `RLIMIT_NPROC`, whichever is larger**. Two sampling-based repairs were tried and
> measured to fail first; do not attempt a third. It remains best-effort and is still meant to be
> **removed**, not extended, when `B-EXEC-04` lands kernel-enforced cgroups v2 `pids.max`.
>
> **Two gate lessons worth keeping:**
> - `tests.py cb <STORY> --kind tooling` selects the **unit tier only** — see `tests.py matrix`. The
>   integration and e2e failures went unmeasured for a day because of it. **Pass `--all` when a
>   change could reach beyond unit, and measure all three tiers before calling a baseline complete.**
> - **Put `.venv/bin` on `PATH`** — `tests/unit/test_architecture.py` shells out to a bare `tach`,
>   which `.venv/bin/python -m pytest` cannot see.
> - **`uv sync`** is now enough — `TECH-028` collapsed the two definitions named `dev` into one
>   dependency-group, so the default command installs every tool the gates need and the whole suite
>   runs on it. `--all-extras` is harmless but no longer required.

## Before Your First Change

Read **[`docs/dev_guides/working_in_this_repo.md`](docs/dev_guides/working_in_this_repo.md)**. It is
ten operational traps, each one an incident that cost a session, with the single line that prevents it.

The four that cost the most, in case you read nothing else:

1. **`$?` after a pipe is `tail`'s, not the gate's.** Two commits landed on a red gate this way. Use
   `python scripts/quality.py cb 2>&1 | tail -3; s=${PIPESTATUS[0]}`.
2. **Put an ABSOLUTE `.venv/bin` on `PATH`** — `export PATH="$PWD/.venv/bin:$PATH"`. A relative entry
   breaks the moment a test `chdir`s into a temp worktree: 45 phantom failures were chased that way.
3. **Break your own guard and watch it fail.** A test that cannot fail is decoration, and this repo
   keeps finding them — a `<= 95` threshold whose debt was cleared, a loop whose match string never
   matched, a `status == "success"` that any cheaper call satisfied.
4. **When a measurement surprises you, suspect the instrument first.** A survey reported 28 delivered
   capabilities in a story that holds 2; the parser had run past the section.

## Where this repo is right now (2026-08-20)

> [!CAUTION]
> **Six capabilities are `🔧`, not `✅`.** `E-VAL-03`, `C-VAL-05`, `B-FLOW-05`, `C-FLOW-11`,
> `B-SENS-03`, `D-UI-01` are built, tested and proven — and the `specweaver-design` **Phase 6
> approval gate has never run for any of them**. `🔧` is not a softer `✅` and not "not started";
> the legend is at the top of the Active Routing Queue. **Nothing automatically stops you flipping
> one to `✅`. Do not.** The evidence is complete; the sign-off is not, and only the user can give
> it.
>
> **Two of them are wrong and say so in their own designs — read those before touching either.**
> `E-VAL-03` does not conform to its specification (it is named *AST* Prompt Injection Sanitization
> and scans rendered text line by line). `B-FLOW-05`'s ceilings sit on `LLMSettings`, and every
> LLM access, payment, pricing, token and limit parameter is to live in **one central place** —
> file or database still undecided.
>
> **Finish the set-back work before proposing anything new.** That includes not opening a new
> capability because it looked like the next thing in a queue.

> [!IMPORTANT]
> **`llm.max_spend_usd` defaults to `$25` and `llm.max_tokens_per_run` to 20,000,000.** A run that
> reaches either stops with `BudgetExceededError` naming the setting. This is deliberate — a
> breaker that ships disabled stops nothing — but it is live, it bills real money below that
> ceiling, and the numbers are placeholders nobody has agreed. Disable with `null`; `0` means
> *refuse everything*, so a mistyped ceiling fails closed.

> [!IMPORTANT]
> **A design starts with `/grill-me <ID>`, which only the user can invoke.** `specweaver-design`
> Phase 1 now ends by telling them to run it and stopping; Phase 6 refuses to present a design
> without a record of what it settled. Two things are never yours to decide: anything that
> **spends money**, and anything that **relaxes a security boundary**. Measured 2026-08-19 — twenty-five
> product-visible decisions were taken by an agent in one session, every one documented in a
> design, and not one agreed. Documenting a guess does not stop it being a guess.

## Critical Rules

1. **No subprocess.** Use `SubprocessExecutor` from `specweaver.sandbox.execution.executor`.
2. **No cross-layer imports.** Respect `tach.toml` boundaries. Run `tach check` to verify.
3. **No guessing.** If anything is unclear, STOP and ask. Never assume.
4. **TDD always.** Red → Green → Refactor. Every change starts with a failing test.
5. **Re-read before edit.** Always read a file immediately before modifying it.
6. **Context files.** Read `context.yaml` in any module before modifying it.

## Commit Convention

**Branching:** Commit **directly to `main` (master)**. Do NOT create feature branches for this repo
(overrides the default "branch first on the default branch" behavior).

Format: `<type>(<scope>): <description>`
Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
Scope: module name (e.g., `flow`, `sandbox`, `graph`, `config`)
Example: `feat(flow): add handover persistence for pipeline state`

## Architecture Reference

For deep architecture docs: `docs/architecture/README.md`
For dev guides: `docs/dev_guides/`
For engineering standards (Antigravity agent): `.agents/AGENTS.md`

## Session Strategy

- **Default (Sonnet):** Use for ~80% of work — coding, tests, refactoring, debugging.
- **Opus (`/model opus` or `claude --model opus`):** Reserve for complex architectural reasoning, multi-module refactors, deep debugging.
- **`opusplan`:** Use when you want Opus for the planning phase and automatic switch to Sonnet for execution.
- **`/compact` at ~60%:** Run proactively before context gets stale. Save state to CLAUDE.md or docs first.
- **`/clear` or new session:** Use when the session has drifted badly, debugging loops are circular, or you're switching to a completely different feature.
- **Subdirectory anchoring:** Launch `claude` from `src/specweaver/core/` (or whichever module you're working on) to limit blast radius. Claude walks up to find this root CLAUDE.md automatically.

<!-- Last verified: 2026-07-12 -->
