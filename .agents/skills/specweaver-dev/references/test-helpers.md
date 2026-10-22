# Test helpers and debugging commands

## Contents
- The two shared test helpers
- Interpreter and parallelism
- Debugging commands

## The two shared test helpers

**Two shared test helpers exist because their absence caused real, cited-proof defects. Use them
rather than re-implementing either.**

**`tests/rendering.py` — `shows(output, needle)` for any assertion on CLI output.** Rich
soft-wraps to the terminal width, so `result.output` can contain `orp\nhan.py`. A raw `in` check
then passes or fails on `COLUMNS`, which nothing in the test declares and CI does not hold
constant. `TECH-017` found this **twice, both times in the cited proof of a delivered contract**,
and both were invisible until the file was run on its own — the full suite stayed green because
xdist sets a different width. `shows()` squashes whitespace on **both** sides. Presence checks
only: never assert layout or ordering with it.

**Setting `COLUMNS` at invoke time does not widen anything.** Rich TRUNCATES table cells to the
terminal width (`fake-journey-model` renders as `fake-j…`), and the CLI's `Console` is built at
module **import** (`interfaces/cli/_core.py:37`) — so `runner.invoke(..., env={"COLUMNS": ...})`
is already too late. `INT-US-16` asserted a model name that way: green run alone, red under
`-n auto`, where xdist's import-time width is narrower. **Assert something width cannot change** —
a parsed number, a row count — rather than a string that might be truncated. And note the mirror
image: asserting a truncated string is ABSENT passes for free, which is how the same commit's
isolation test was vacuous until it counted rows instead.

**`tests/scripted_llm.py` — `doubled_llm()` / `scripted_world()` when a test needs a doubled LLM.**
Every model call takes one path, `RoleResolver`, so these patch that one class: commands, the
router and the REST API are all covered. `doubled_llm` also stands in for the `[brake]` values, so
a test's settings file need not spell them out. Never add a second way to build an adapter — two paths
is how `INT-US-02`'s e2e once made a live API call while reading as mocked. `FixedRouter` gives a
hand-built `RunContext` its router; `TEST_CONFIG` gives a hand-built workflow class its settings.
Import them explicitly rather than hiding them in a fixture: the import line is the only place a
reader sees that a test doubles the model. `tests/fake_http.py` fakes HTTP for SDKs on `httpx2`.

## Interpreter and parallelism

**Interpreter + parallelism.** Every command in this skill uses a bare `python` for brevity, but
run them with the project venv, `.venv/bin/python`: the system interpreter imports `specweaver` fine but has **no `pytest-xdist`**, so
`-n auto` silently does nothing there and the suite runs serial.

The single-file commands below are deliberately serial — measured on 16 cores, one module is
12.5s serial vs 15.2s with `-n auto`, because worker startup costs more than it saves. Add
`-n auto` only once you are running a whole tier or the full suite (`tests/unit` 5m02 -> 1m37;
full suite ~13m -> 4m26). `scripts/tests.py` already passes `-n auto`, so the commit-boundary
gate in Phase 4/5 needs nothing extra.

## Debugging commands

When a test fails and you need to debug, run targeted tests autonomously.
All these commands auto-run — no human interaction needed:
```
# Single test by node ID
python -m pytest tests/unit/test_foo.py::TestClass::test_method -v --tb=long

# Keyword filter
python -m pytest tests/unit/test_foo.py -k "test_specific_case" -v --tb=long

# All tests in a specific file with full traceback
python -m pytest tests/unit/test_foo.py -v --tb=long

# Re-run only previously failed tests
python -m pytest --lf -v --tb=long

# Run test with debug logging enabled
python -m pytest tests/unit/test_foo.py -s --log-cli-level=DEBUG

# Run arbitrary python debug scripts via file (must be safe)
# write your script to .tmp/debug.py then run:
python .tmp/debug.py
```

Debug loop: read error → re-read source → fix → re-run failing test → repeat until green.
