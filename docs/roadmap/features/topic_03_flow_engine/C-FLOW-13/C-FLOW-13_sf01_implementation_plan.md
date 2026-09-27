# C-FLOW-13 SF-01 — Settings and Layering

**Status**: APPROVED — approved by Steve Bula `[agreed 2026-09-26]` · **FRs owned**: FR-1, FR-2, FR-3, FR-4, FR-5 · **Depends on**:
none · Design: [C-FLOW-13_design.md](C-FLOW-13_design.md) §Sub-features → SF-01

## Goal

Read the machine file and the project `[llm]` section, validate each strictly, and resolve one
setting per role with its origin — shown by `sw config show`. Nothing else reads these files yet:
consumers switch over in SF-03, so SF-01 changes no run's behaviour.

## Where it plugs in

| Fact | Where |
|---|---|
| Data dir: `specweaver_root() -> Path`, honours `SPECWEAVER_DATA_DIR`; machine file = `specweaver_root() / "settings.toml"` | `core/config/paths.py:28-41` |
| Project root: `proj.get("root_path")` from the project registry | `core/config/bootstrap/settings_loader.py:198` |
| Two existing `specweaver.toml` readers swallow parse errors (`logger.exception`, defaults) — the pattern FR-4 forbids for `[llm]` | `settings_loader.py:49-86` |
| `core.config` is pure-logic (no I/O); `core.config.bootstrap` is the I/O adapter; `core.config.interfaces` (the `sw config` commands) may import `core.config`, `infrastructure.llm`, `interfaces.cli`, `assurance.validation` — **not** `core.config.bootstrap` | `tach.toml:33-42` |
| `config_app = typer.Typer(...)`, 501 lines, commands registered with `@config_app.command(...)` | `core/config/interfaces/cli.py:24` |
| TOML: `tomllib` reads (stdlib); `tomlkit.parse` gives a document that keeps positions | `workspace/project/tach_sync.py:86` |
| On Python 3.11–3.13 `tomllib.TOMLDecodeError` has no `lineno`; the line is in the message ("at line N, column M") | Python docs, `tomllib` |

## Changes

**CB-1 — models and strict parsing (pure)**

1. `core/config/llm_settings.py` (new, pure): pydantic models, all `extra="forbid"`:
   `ServerEntry(kind, base_url=None, api_key_env=None, private: bool, max_parallel: int ≥ 1)`,
   `RoleEntry` — a string `"model@server"` or a table `{model = "model@server", temperature?,
   max_output_tokens?, top_p?, top_k?}`, `BrakeValues(hosted_chf_per_run, local_gpu_hours_per_run,
   agent_turns)`, `Currency(usd_to_chf, rate_date)`, `ModelFacts(...)` (fields the catalogue will
   carry; SF-02 fills them), `MachineLlmFile(schema_version, currency, servers, roles, brake, models)`,
   `ProjectLlmSection(private_only: bool = False, roles)`. Role keys are the existing task types —
   `draft`, `review`, `plan`, `implement`, `validate`, `check` — plus `default`; any other key is a
   typo and refused.
2. Same module: `parse_machine_file(text: str, source: str) -> MachineLlmFile` and
   `parse_project_llm(text: str, source: str) -> ProjectLlmSection` — pure, text in, model out.
   Each raises `SettingsFileError(source, key, line, message)`:
   1. TOML syntax error → line from the `tomllib` message.
   2. Validation error → `loc` → key path → line found by scanning the source text for the table
      header and then the key (neither `tomllib` nor `tomlkit` exposes line numbers).
   3. Project file with `servers`, `base_url` or `api_key_env` anywhere → the FR-5 message
      ("a project may choose models, not define where code is sent — set servers in <machine file>").
3. Unknown `schema_version` → `SettingsFileError` with an upgrade message (NFR-5).

**CB-2 — layering, file reading, `sw config show`**

4. `core/config/llm_settings.py`: `resolve_roles(machine, project, run_override=None) ->
   dict[str, ResolvedRole]` — pure. Order: machine → project → run override (catalogue defaults are
   the lowest layer, added in SF-02 through an optional facts argument). Each `ResolvedRole` carries
   `model`, `server`, sampling, and an `origin` per field (`"<file>:<key>"` or `"run --model"`).
   A role naming a server that no machine entry defines → `SettingsFileError` naming the role.
5. `core/config/bootstrap/llm_settings_loader.py` (new): `load_llm_settings(project_root: Path |
   None) -> tuple[MachineLlmFile, ProjectLlmSection]` — the only reader of both files (NFR-4).
   Missing machine file → defaults (FR-1); missing `specweaver.toml` or no `[llm]` → empty section.
   Until SF-03 switches the consumers, only `sw config show` calls it, so FR-4's refusal is proven
   there; SF-03 extends it to every command that resolves LLM settings.
6. `sw config show`: prints every resolved role, server, brake value and currency with its origin
   (`built-in default` when no file sets it). It imports the loader through the dependency agreed in Q-1.

| File | Change | FR |
|------|--------|-----|
| `src/specweaver/core/config/llm_settings.py` | models, parsers, `SettingsFileError`, `resolve_roles` | FR-2, FR-3, FR-4, FR-5 |
| `src/specweaver/core/config/bootstrap/llm_settings_loader.py` | file reading, missing-file defaults | FR-1, FR-2 |
| `src/specweaver/core/config/interfaces/cli.py` (or a sibling file, see Q-1) | `sw config show` | FR-3, FR-4 |
| `tach.toml` | `specweaver.core.config.interfaces` depends on `specweaver.core.config.bootstrap` | — |

## Tests

| Tier | Bucket | Case | FR |
|---|---|---|---|
| Unit | Happy | a full machine file parses; every field has its type | FR-1 |
| Unit | Boundary | empty file, `max_parallel = 0`, role string without `@` | FR-4 |
| Unit | Degradation | missing machine file → defaults; missing `[llm]` → empty section | FR-1, FR-2 |
| Unit | Hostile | unknown key `temprature` → error names file, key and line; wrong type; bad TOML syntax → line; a key value containing a secret never appears in the message (NFR-2) | FR-4 |
| Unit | Hostile | project file with `[servers.x]`, `base_url`, `api_key_env` → refused with the FR-5 message | FR-5 |
| Unit | Happy/Boundary | layering: project beats machine per role; `--model` beats both; role table overrides sampling; origins name file and key | FR-3 |
| Unit | Degradation | role pointing at an undefined server → refused, naming the role | FR-3 |
| Integration | Happy | `load_llm_settings` reads real files under a temp `SPECWEAVER_DATA_DIR` and a temp project | FR-1, FR-2 |
| E2E (P4, P7) | Journey | `sw config show` in a temp project: shows values with origins; a typo in the machine file → non-zero exit naming file and line; a project file setting a server → refused | FR-3, FR-4, FR-5 |

Written first and seen red. Mutants to record: drop `extra="forbid"` (typo passes silently);
reverse the layering order; remove the project `servers` refusal.

Commit boundaries: CB-1 (items 1–3, unit tests), CB-2 (items 4–6, unit + integration + e2e P4/P7).

## Decisions (audit)

| # | Question | Options | Proposal |
|---|----------|---------|----------|
| Q-1 | `sw config show` must read the files, but `core.config.interfaces` may not import `core.config.bootstrap` (`tach.toml:42`) | (a) allow `core.config.interfaces → core.config.bootstrap` in `tach.toml`; (b) the command reads the files itself (a second reader, breaking NFR-4); (c) put the command in `interfaces.cli`, which may import bootstrap **(a)** `[agreed 2026-09-26]` — a CLI depending on the bootstrap adapter is the normal direction (`interfaces.cli` already does); one reader stays one reader |
| Q-2 | Allowed `kind` values for a server (a name other code depends on) | the five existing provider names `gemini`, `openai`, `anthropic`, `mistral`, `qwen`, plus `openai-compatible` for vLLM, Ollama and similar | **as listed** `[agreed 2026-09-26]` |
| Q-3 | `api_key_env` omitted for a hosted kind | (a) default to the adapter's variable (`ANTHROPIC_API_KEY`, …); (b) required | **(a)** `[agreed 2026-09-26]` — the adapters already declare it (`api_key_env_var`); `openai-compatible` defaults to none (keyless) |

## As built (2026-09-27)

Committed in two boundaries: `b3c501bc` (models, strict parsing) and `1e615931` (reader, layering,
`sw config show`).

- `sw config show` lives in `core/config/interfaces/llm_show.py`, registered on `config_app`, so
  `cli.py` grows by two lines; the rows come from the pure `settings_report`.
- A typo is reported before the "missing" error it causes (both are raised by pydantic).
- `pyproject.toml` marks `pydantic.BaseModel` subclasses runtime-evaluated for ruff; two `noqa`
  became unused and went.
- Mutants: [C-FLOW-13_mutants.json](C-FLOW-13_mutants.json), 6, all protected.
- Found on the way and fixed separately (`87dd3a2e`): the database semaphore was shared across event
  loops.

