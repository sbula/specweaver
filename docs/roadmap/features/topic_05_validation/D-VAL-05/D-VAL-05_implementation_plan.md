# D-VAL-05 — Code Validation Rules: as built

**Design**: [D-VAL-05_design.md](D-VAL-05_design.md)

| File | Holds | FRs |
|:---|:---|:---|
| `assurance/validation/rules/code/c01_syntax_valid.py` … `c08_type_hints.py` | the rules, pure logic | FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 |
| `core/flow/handlers/validation_hydrator.py` | runs the test, coverage and architecture checks; names the test file | FR-3, FR-4, FR-5 |
| `sandbox/language/core/python/runner.py` | pytest with the module's folder on `PYTHONPATH`; `tach` only with a `tach.toml` | FR-3, FR-5 |
| `core/flow/handlers/validation.py` | `run_tests` passes the generated module as `source` | FR-3 |
