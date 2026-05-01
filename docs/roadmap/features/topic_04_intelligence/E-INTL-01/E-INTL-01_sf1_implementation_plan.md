# E-INTL-01 — LLM Adapter (Implementation Plan)

### Step 3: LLM Adapter + Remaining Rules (2-3 sessions)

**Copy from FM:**
- `llm/provider.py` → `llm/adapter.py` (simplified)
- `llm/errors.py` (trimmed)
- `llm/adapters/gemini_adapter.py` → `llm/gemini_adapter.py` (simplified)
- `security/redactor.py` → `llm/redactor.py`
- `engine/security.py` → `project/safepath.py`
- LLM test files (adapted)

**Create:**
- 3 remaining spec rules: S03, S04, S07
- Adapter integration with validation runner

**Runnable:** All 11 spec validation rules operational

---
