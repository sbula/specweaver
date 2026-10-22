---
name: specweaver-live-llm
description: >-
  Runs the `live`-marked tests against real LLM providers and reads their verdict. Use only when
  the user types /specweaver-live-llm: 'run the live tests', 'test against real Gemini', 'verify
  my API key works'. Never part of implementing a feature, never at a commit boundary, never to
  'check' something an offline test can answer.
argument-hint: "[nightly | status | <test node id>]"
disable-model-invocation: true
---

# Live LLM Tests

```
Trigger: "run the live tests", "test against real Gemini",
         "does my API key work", "hit the real API"
```

> [!CAUTION]
> **This skill spends the user's money.** Every run bills a real provider. It is opt-in, invoked
> by hand, and never a step inside another task. Only the user starts it, with
> `/specweaver-live-llm` `[agreed 2026-10-22]`.
>
> **Do NOT invoke this skill when:**
> - implementing, refactoring or debugging anything — the offline suite is the feedback loop;
> - running a commit boundary. `quality.py cb` and `quality.py doc` never touch a live API, and
>   `scripts/tests.py` never selects the marker;
> - an offline test could answer the question. It almost always can.
>
> The default `pytest` run already deselects these (`-m 'not live and not toolchain'` in
> `pyproject.toml`), and `tests/unit/test_live_marker_isolation.py` fails if that protection is
> ever removed. Do not "fix" that guard to make a live run more convenient.

## Two kinds of live test, two places for the key

| Kind | Where | Reads its key from | No key means |
|---|---|---|---|
| **Nightly e2e** | `tests/e2e/capabilities/**/test_*_live_e2e.py` | `~/.specweaver/keys.env`, the file SpecWeaver itself uses | the test **fails** |
| **Manual adapter checks** | `tests/manual/test_llm_live.py` | one shell variable per provider | the test **skips** |

**SpecWeaver reads API keys only from `~/.specweaver/keys.env`** (chmod 600), never from the shell
or a project `[agreed 2026-10-11]` — `src/specweaver/core/config/bootstrap/llm_settings_loader.py`.
`specweaver.toml` cannot hold a key and the database never stores one. Each server in the settings
names its key's variable in `api_key_env`.

The manual checks build an adapter directly and take the key from the shell: `GEMINI_API_KEY`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `DASHSCOPE_API_KEY` (Qwen; the live test
also needs `DASHSCOPE_BASE_URL`, your workspace address). There is no dotenv support in the
codebase, so a `.env` file does nothing until something sources it. `.env` and `.envrc` are already
in `.gitignore`. A key file at the repo root is safe from git, and should be `chmod 600`.

> [!IMPORTANT]
> **Never read, print or copy a key file, and never echo a command that contains a key.** Check
> presence, not value: `python -c "import os; print(bool(os.environ.get('GEMINI_API_KEY')))"`.
> A missing key in `keys.env` is the user's to add; say which variable is missing and stop.

## Running

```bash
export PATH="$PWD/.venv/bin:$PATH"

# the nightly run, now: every live test, keys from ~/.specweaver/keys.env
python scripts/live.py

# the last nightly verdict; exit 1 unless it passed
python scripts/live.py --status

# one manual check, the cheapest useful test of a shell key
set -a; source .env; set +a
python -m pytest tests/manual/test_llm_live.py::test_llm_live_gemini_connection -m live -v
```

`scripts/live.py` points the tests at the real key file through `SPECWEAVER_LIVE_KEYS`; the test
session itself runs on a separate data directory. Each live test sets its own spend limit; together
they stay under **USD 0.10 a night** `[agreed 2026-10-10]`. The key is on the free tier:
`tests/e2e/gemini_budget.py` sends at most 20 Gemini requests, and a test the quota stops is
skipped as `provider quota` and counted in the verdict `[agreed 2026-10-14]`. The full log is
`.tmp/live/last.log`.

`-m live` is required when you call pytest yourself. Without it the marker filter in `addopts`
deselects the tests and pytest reports `deselected`, not `passed`.

## Reading the result

| Outcome | Means |
|---|---|
| `passed` | The key works and the provider answered. |
| `skipped` (manual check) | **No key in this shell.** The test skips itself rather than fail — `source .env` first. A skip is never evidence the key is good. |
| `skipped` as `provider quota` | The free-tier quota stopped it. Counted in the verdict; not a pass. |
| `failed`, key missing | A nightly e2e found no key in `keys.env`. Only the user can add it. |
| `failed` on auth | The key is set but rejected. `GeminiAdapter` logs which variable to check. |
| `failed` on the assertion | The provider answered something unexpected. Check the model name in the test is still offered. |
| `ERROR` from the spend brake | A test's `[brake]` limit stopped the run. Read the log: the limit may be too low, or a call grew dearer. Changing a limit is the user's call (`T-SPEND`). |

`skipped` is the outcome that misleads. It looks like nothing is wrong.

## The sandbox strips these keys on purpose

`_CREDENTIAL_VARS` in `src/specweaver/sandbox/execution/child_env.py` removes every provider key
from any sandboxed child process, **even when passed through `extra_env`**. That is a red-team
control, not a bug: it stops generated code from exfiltrating the key.

So a live test must call the adapter directly, the way `tests/manual/test_llm_live.py` does. A test
that shells out through `SubprocessExecutor` and expects to reach a provider will always see an
empty key. Do not weaken that list to make such a test pass.

When the run is done, report the verdict in one line and end with `Push now: YES/NO`.
