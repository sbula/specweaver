# E-INTL-01 SF-01 — LLM Adapter & Rules

**Phase**: 1, build step 3 · Design: [E-INTL-01_design.md](E-INTL-01_design.md)

## Goal

LLM adapter + the remaining spec rules. **Runnable:** all 11 spec validation rules operational.

## Changes

**Copied from FM:**

- `llm/provider.py` → `llm/adapter.py` (simplified)
- `llm/errors.py` (trimmed)
- `llm/adapters/gemini_adapter.py` → `llm/gemini_adapter.py` (simplified)
- `security/redactor.py` → `llm/redactor.py`
- `engine/security.py` → `project/safepath.py`
- LLM test files (adapted)

**Created:**

- 3 remaining spec rules: S03, S04, S07
- Adapter integration with validation runner

**Since moved** (noted 2026-09-25): the Gemini adapter lives at
`src/specweaver/infrastructure/llm/adapters/gemini.py`; the validation runner at
`src/specweaver/assurance/validation/runner.py`.
