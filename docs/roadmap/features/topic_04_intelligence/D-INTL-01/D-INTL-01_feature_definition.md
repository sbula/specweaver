# D-INTL-01 — Implementation Generator

### F5: Implementation (`sw implement`)

Reads validated+reviewed spec, generates code + tests:
- From Contract: signatures, types, docstrings
- From Protocol: method bodies
- From Policy: configurable parameters
- From examples: test cases
- Output: `<name>.py` + `test_<name>.py` in the target project
- LLM required

### F7: Code Review (`sw review code`)

LLM semantic evaluation of code against its source spec. Reviewer is read-only. Output: ACCEPTED or DENIED with findings. Same approach as F4.

---
