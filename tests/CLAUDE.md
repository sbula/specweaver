# Tests

## Structure

```
tests/
├── unit/          # Fast, isolated. Mock all I/O. Target: <2s per file.
├── integration/   # Multi-layer. Mock external APIs only.
├── e2e/           # Full real-world scenarios. CLI invocations.
│   └── capabilities/<domain>/   # every e2e lives here — see below
├── assurance/     # Quality assurance tests (standards, validation).
├── fixtures/      # Shared test data (YAML specs, sample configs).
└── manual/        # Manual test scripts (not in CI).
```

## Markers

- `@pytest.mark.live` — Requires real API keys + network. Excluded by default.
- `@pytest.mark.integration` — Multi-layer tests with mocked externals.
- `@pytest.mark.e2e` — End-to-end CLI scenarios.

## Adversarial Test Matrix (4 Buckets)

Every feature MUST have tests in all 4 buckets:

1. **Happy Path** — Expected input → expected output.
2. **Boundary/Edge Cases** — Empty inputs, max constraints, cyclic graphs, Unicode.
3. **Graceful Degradation** — Dependencies failing, timeouts, malformed data.
4. **Hostile/Wrong Input** — Path traversal, wrong types, None injection, SQL injection strings.

## e2e layout is enforced

Every e2e test lives in `tests/e2e/capabilities/<domain>/`, where `<domain>` mirrors a `src/specweaver`
macro-domain. A loose file at the tier root **fails** `tests/unit/test_macro_domain_layout.py` — it is
not an exception list to add to. The one directory outside that rule is `tests/e2e/scripts/`, which
drives the repo's own dev tooling and has no product capability to sit under.

The unit and integration tiers mirror `src/specweaver` package-for-package, with `scripts` and
`alembic` the only exceptions — each mirrors a repo-root directory rather than nothing.

## Conventions

- Fixtures live in `tests/fixtures/` or per-module `conftest.py`.
- Use `pytest-asyncio` with `asyncio_mode = "auto"` (configured in `pyproject.toml`).
- Use `respx` for HTTP mocking, NOT `unittest.mock.patch` on HTTP clients.
- Coverage target: 70-90%.
- **`tests`, plural, is the name.** The tree, any directory in it, and any identifier naming a
  collection of tests use the plural. The singular is correct in exactly two places: one test
  (`test_name`, the `test_` function prefix), and a token a foreign tool mandates — `mvnw test`,
  `cargo test`, Maven's `src/test/java`, the stdlib `test` module. Never as our own choice.

## Quick Commands

```bash
# Run only previously failed tests
python -m pytest --lf -v --tb=long

# Run by keyword
python -m pytest -k "test_specific_name" -v --tb=long

# Run with coverage
python -m pytest --cov=specweaver --cov-report=term-missing tests/unit/
```

<!-- Last verified: 2026-07-12 -->
