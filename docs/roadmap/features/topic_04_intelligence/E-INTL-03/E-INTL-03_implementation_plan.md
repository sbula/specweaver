# E-INTL-03 — Spec Review Engine: as built

**Design**: [E-INTL-03_design.md](E-INTL-03_design.md)

| File | Holds | FRs |
|:---|:---|:---|
| `workflows/review/interfaces/cli.py` | `sw review`: one review step, the printed result, the exit code | FR-1, FR-2, FR-3 |
| `workflows/review/reviewer.py` | `Reviewer`: prompt, call, verdict line, findings | FR-1, FR-2, FR-3, FR-4 |
| `core/flow/handlers/review.py` | the review steps: tools, mentioned files between rounds | FR-4 |
