# Tests

## Structure

```
tests/
├── unit/          # Fast, isolated. Mock all I/O. Target: <2s per file.
├── integration/   # Multi-layer. Mock external APIs only.
├── e2e/           # Full real-world scenarios. CLI invocations.
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

## Conventions

- Fixtures live in `tests/fixtures/` or per-module `conftest.py`.
- Use `pytest-asyncio` with `asyncio_mode = "auto"` (configured in `pyproject.toml`).
- Use `respx` for HTTP mocking, NOT `unittest.mock.patch` on HTTP clients.
- Coverage target: 70-90%.

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
