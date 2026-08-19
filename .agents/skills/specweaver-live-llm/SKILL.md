---
name: specweaver-live-llm
description: "Run the `live`-marked tests against a real LLM provider. ONLY when the user
explicitly asks to hit a real API — 'run the live tests', 'test against real Gemini', 'verify my
API key works'. Never as part of implementing a feature, never at a commit boundary, never to
'check' something an offline test can answer."
---

# Live LLM Tests

```
Trigger: "run the live tests", "test against real Gemini",
         "does my API key work", "hit the real API"
```

> [!CAUTION]
> **This skill spends the user's money.** Every run bills a real provider. It is opt-in, invoked
> by hand, and never a step inside another task.
>
> **Do NOT invoke this skill when:**
> - implementing, refactoring or debugging anything — the offline suite is the feedback loop;
> - running a commit boundary. `quality.py cb` and `quality.py doc` never touch a live API, and
>   `scripts/tests.py` never selects the marker;
> - an offline test could answer the question. It almost always can — 7873 of them do.
>
> The default `pytest` run already deselects these (`-m 'not live'` in `pyproject.toml`), and
> `tests/unit/test_live_marker_isolation.py` fails if that protection is ever removed. Do not
> "fix" that guard to make a live run more convenient.

## The credential

One environment variable per provider. `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`MISTRAL_API_KEY`, `QWEN_API_KEY`.

**The environment is the only place it can live.** `specweaver.toml` cannot hold it and the
database never stores it — `src/specweaver/core/config/bootstrap/settings_loader.py` reads
`os.environ` and nothing else. There is no dotenv support in the codebase either, so a `.env` file
does nothing until something sources it.

`.env` and `.envrc` are already in `.gitignore`. A key file at the repo root is safe from git, and
should be `chmod 600`.

```bash
# one session, nothing written to disk
export GEMINI_API_KEY="…"

# or a project file, sourced on demand
set -a; source .env; set +a
```

> [!IMPORTANT]
> **Never print the key, and never echo a command that contains it.** Check presence, not value:
> `python -c "import os; print(bool(os.environ.get('GEMINI_API_KEY')))"`.

## Running

```bash
export PATH="$PWD/.venv/bin:$PATH"
set -a; source .env; set +a

# one provider, one test — the cheapest useful check
python -m pytest tests/manual/test_llm_live.py::test_llm_live_gemini_connection -m live -v

# every live test
python -m pytest -m live -v
```

`-m live` is required. Without it the marker filter in `addopts` deselects them and pytest reports
`deselected`, not `passed`.

## Reading the result

| Outcome | Means |
|---|---|
| `passed` | The key works and the provider answered. |
| `skipped` | **No key in this shell.** The tests skip themselves rather than fail — `source .env` first. A skip is never evidence the key is good. |
| `failed` on auth | The key is set but rejected. `GeminiAdapter` logs which variable it read. |
| `failed` on the assertion | The provider answered something unexpected. Check the model name in the test is still offered. |

`skipped` is the outcome that misleads. It looks like nothing is wrong.

## The sandbox strips these keys on purpose

`_CREDENTIAL_VARS` in `src/specweaver/sandbox/execution/executor.py` removes every provider key
from any sandboxed child process, **even when passed through `extra_env`**. That is a red-team
control, not a bug: it stops generated code from exfiltrating the key.

So a live test must call the adapter directly, the way `tests/manual/test_llm_live.py` does. A test
that shells out through `SubprocessExecutor` and expects to reach a provider will always see an
empty key. Do not weaken that list to make such a test pass.
