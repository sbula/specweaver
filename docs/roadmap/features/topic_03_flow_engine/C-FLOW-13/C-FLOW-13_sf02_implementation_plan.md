# C-FLOW-13 SF-02 — Catalogue, Servers, Privacy

**Status**: APPROVED — approved by Steve Bula `[agreed 2026-09-27]` · **FRs owned**: FR-6, FR-7, FR-8, FR-9, FR-18 · **Depends on**: SF-01 (committed) ·
Design: [C-FLOW-13_design.md](C-FLOW-13_design.md) §Sub-features → SF-02

## Goal

Give every model its facts from one shipped catalogue, build every adapter client from a server
entry, limit parallel calls per server, and refuse a hosted server in a private-only project.
Consumers do not switch yet (SF-03), so no command's behaviour changes except `sw config show`,
which now also reports the privacy rule.

## Where it plugs in

| Fact | Where |
|---|---|
| `ModelFacts(context, max_output, tool_calls, sampling)`; `MachineLlmFile.models: dict[str, ModelFacts]`; `resolve_roles(files, run_overrides)` | `core/config/llm_settings.py:110,140` |
| `infrastructure.llm` may import `core.config`, not `core.config.bootstrap` | `tach.toml:57-58` |
| Adapters: `__init__(api_key=None)`; clients `AsyncOpenAI(api_key)` `openai.py:77`, `AsyncAnthropic(api_key)` `anthropic.py:70`, `genai.Client(api_key)` `gemini.py:97`, `Mistral(api_key)` `mistral.py:79`; Qwen hard-codes `base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"` `qwen.py:38` | adapters |
| SDK address parameters: `AsyncOpenAI(base_url=)`, `AsyncAnthropic(base_url=)`, `genai.Client(http_options={"base_url": ...})`, `Mistral(server_url=)`; env fallbacks `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, `GOOGLE_GEMINI_BASE_URL` | installed openai 2.30, anthropic 0.86, google-genai 1.66, mistralai 2.1.3 |
| `AsyncOpenAI` refuses `api_key=None` when `OPENAI_API_KEY` is unset | `openai/_client.py:479` |
| Limiter: one global `_PROVIDER_SEMAPHORES: dict[str, Semaphore]` keyed by provider, first limit wins, 30 s slot timeout — shared across event loops (same defect as the DB one fixed in `87dd3a2e`) | `adapters/_rate_limit.py:15-60`; built in `factory.py:127` |
| models.dev: MIT; `https://models.dev/api.json` (~4.9 MB, 403 without a User-Agent); shape `{provider: {models: {id: {cost{input,output,reasoning?}, limit{context,output}, tool_call, temperature, reasoning, status?}}}}`, USD per 1M tokens; provider ids `google, openai, anthropic, mistral, alibaba`; `api.json` is built, never committed, so no commit serves it | research 2026-09-27 |
| Output cap includes thinking: OpenAI yes (`max_completion_tokens`), Anthropic yes (`max_tokens`), Gemini yes (`max_output_tokens`), Mistral unverified, Qwen no (separate `thinking_budget`) | provider docs, see research |

## Changes

**CB-1 — privacy rule (pure)** · FR-9

1. `resolve_roles` refuses, after layering, any role whose server has `private = false` when the
   project sets `private_only = true` — run overrides included. `SettingsFileError` names the rule,
   the role, the server and the line of `private_only`.
2. `sw config show` exits 1 with that message (it already exits 1 on `SettingsFileError`).

**CB-2 — catalogue** · FR-6, FR-18

3. `infrastructure/llm/catalogue/models_dev.json` (generated, never hand-edited): `schema_version`,
   `source {url, fetched, etag, repo_commit}`, `models {"<kind>/<model>": {...}}` for the five hosted
   kinds, non-deprecated models only, fields: prices, context, max output, tool calling.
4. `infrastructure/llm/catalogue/local.toml` (hand-written, credited, wins over the generated file):
   per-kind `thinking_in_output_cap`, sampling defaults, notes (the vLLM `qwen3_xml` parser).
5. `infrastructure/llm/catalogue.py`: `model_facts(kind, model, overrides) -> ModelFacts | None`.
   Order: generated → local → machine `[models."<id>"]`. An `openai-compatible` server is never
   matched against hosted entries (Q-3). Unknown `schema_version` refuses (NFR-5). Read once per
   process.
6. `ModelFacts` gains the two price fields and `thinking_in_output_cap` (names: Q-2).
7. `scripts/update_model_catalogue.py`: fetch, keep the five kinds, drop `status = "deprecated"`,
   convert, stamp, write sorted JSON so the diff is the review (Q-1). A pure `convert(api: dict) ->
   dict` does the work; the fetch is one function.

**CB-3 — adapters from servers, limit per server** · FR-7, FR-8

8. `infrastructure/llm/servers.py`: `adapter_for_server(name: str, server: ServerEntry) -> LLMAdapter`.
   Steps: kind → adapter class (`openai-compatible` → the OpenAI adapter); key from the env var the
   entry names, or none; `base_url` from the entry, else the kind's official address written out
   (AD-4: no SDK env fallback can win); wrap in the limiter keyed by server name with `max_parallel`.
   Gemini gets `vertexai=False` explicitly, so `GOOGLE_GENAI_USE_VERTEXAI` cannot reroute it.
9. Each adapter's `__init__` takes `base_url: str` and passes it to its client. Keyless: the OpenAI
   client gets a fixed placeholder key, and `available()` is true for a keyless server.

   > [!CAUTION]
   > Never pass `api_key=None` to `AsyncOpenAI`: it then reads `OPENAI_API_KEY` and sends the user's
   > OpenAI key to the GB10 or any other `openai-compatible` address.
10. `_rate_limit.py`: one semaphore per (event loop, key), `WeakKeyDictionary` per loop as in
    `database.py`; the factory keeps passing the provider name until SF-03. No slot timeout (Q-4),
    so a slot must be released on every exit — error, cancel, and a stream closed early.
11. Q-5 fixes, if agreed: Mistral imports `mistralai.client.Mistral` and `mistralai.client.errors`,
    `pyproject.toml` pins `mistralai>=2.1`; the `openai` kind sends `max_completion_tokens`;
    `qwen` and `openai-compatible` keep `max_tokens` (DashScope, vLLM and Ollama all accept it).
    Qwen keeps today's address and `QWEN_API_KEY` as its defaults.

| File | Change | FR |
|------|--------|-----|
| `src/specweaver/core/config/llm_settings.py` | privacy check; `ModelFacts` fields | FR-9, FR-6 |
| `src/specweaver/infrastructure/llm/catalogue.py`, `catalogue/*.json`, `catalogue/local.toml` | new | FR-6 |
| `scripts/update_model_catalogue.py` | new | FR-18 |
| `src/specweaver/infrastructure/llm/servers.py` | new | FR-7, FR-8 |
| `src/specweaver/infrastructure/llm/adapters/*.py` | `base_url`; keyless | FR-7 |
| `src/specweaver/infrastructure/llm/adapters/_rate_limit.py` | per loop, per key | FR-8 |
| (inside `models_dev.json`) | `source.license`: the models.dev MIT notice, so it ships with the data | FR-18 |

## Tests

| Tier | Bucket | Case | FR |
|---|---|---|---|
| Unit | Happy | private-only project, all roles on private servers → resolves | FR-9 |
| Unit | Hostile | private-only project, role on a hosted server → refused, names role and server; same through a run override | FR-9 |
| Unit | Boundary | `private_only` unset → hosted allowed | FR-9 |
| Unit | Happy | `convert` on a small api.json fixture → kinds kept, prices per 1M, deprecated dropped, stamp present | FR-18 |
| Unit | Boundary | machine override beats local beats generated, field by field | FR-6 |
| Unit | Degradation | unknown model → `None`, not zeros; unknown `schema_version` → refused | FR-6 |
| Unit | Hostile | `openai-compatible` model with a hosted namesake → not matched | FR-6 |
| Integration | Happy | the shipped catalogue loads, validates, under 50 ms (NFR-1); settings file → `model_facts` with the machine override | FR-6 |
| Unit | Happy | each kind's client gets the entry's `base_url`, else the official address | FR-7 |
| Unit | Hostile | `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL` set → ignored | FR-7 |
| Unit | Boundary | keyless `openai-compatible` → `available()` true | FR-7 |
| Unit | Hostile | `OPENAI_API_KEY` set, keyless GB10 server → the request carries the placeholder, never that key | FR-7 |
| Unit | Degradation | two servers of the same kind get separate slots; two event loops get separate semaphores | FR-8 |
| Unit | Degradation | a failing call, a cancelled call and an early-closed stream each free their slot | FR-8 |
| Integration (P2 seam) | Happy | settings text with the GB10 → resolve the role → `adapter_for_server` → `generate` → respx sees `http://gb10:8000/v1/chat/completions` with no key | FR-7 |
| Integration | Boundary | `max_parallel = 2`, three calls → the third waits | FR-8 |
| E2E (P2, P3) | Journey | `sw run` step sends to the GB10; private-only run refuses before any call — `xfail(strict=True, reason="blocked on C-FLOW-13 SF-03: consumers not switched")` | FR-7, FR-9 |

Written first and seen red. Mutants to record: drop the privacy check; reverse the override order;
key the limiter by kind instead of server; drop `base_url` from the OpenAI client; honour
`OPENAI_BASE_URL`.

Commit boundaries: CB-1 (items 1–2), CB-2 (items 3–7), CB-3 (items 8–11, with the P2 seam test and
the two xfail e2e).

## Decisions (audit)

| # | Question | Options | Proposal |
|---|----------|---------|----------|
| Q-1 | FR-18 says "pinned models.dev commit", but no commit holds `api.json` | (a) fetch the live file; stamp date, ETag and repo head commit; the committed catalogue is the pin and its diff the review; (b) rebuild from the per-commit TOML sources, re-implementing their inheritance rules | **(a)** — same reviewable diff, a fraction of the code; FR-18 wording changes to match `[agreed 2026-09-27]` |
| Q-2 | Field names for prices in `[models."<id>"]` | (a) `usd_per_million_input`, `usd_per_million_output`; (b) models.dev style `cost = { input, output }` | **(a)** — today's adapters price per 1K, models.dev per 1M; the unit in the name stops that mix-up. Plus `thinking_in_output_cap` `[agreed 2026-09-27]` |
| Q-3 | A model on the GB10 with the same name as a hosted one | (a) no match: facts only from `[models."<id>"]` and `local.toml`; price unknown; (b) borrow the hosted entry | **(a)** — the hosted price is wrong for your own box; local cost is the brake's GPU hours `[agreed 2026-09-27]` |
| Q-4 | Waiting for a free slot: today 30 s, then error; a GB10 answer can take minutes | (a) no slot timeout — the SDK's request timeout still ends a hung call; (b) new server key `queue_timeout` with a default | **(a)** — no new key; a queued call no longer fails only because the box is busy `[agreed 2026-09-27]` |
| Q-5 | Two live defects in the adapters CB-3 rewrites: Mistral cannot import with the installed SDK; OpenAI sends deprecated `max_tokens` (o-series refuse it; it does not cap thinking) | (a) fix both in CB-3; (b) leave them, file a TECH ticket | **(a)** — same lines, small change, no ticket `[agreed 2026-09-27]` |
