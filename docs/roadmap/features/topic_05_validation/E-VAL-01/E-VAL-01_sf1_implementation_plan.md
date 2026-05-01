# E-VAL-01 — Core Validation Engine (Implementation Plan)

### Step 2: Validation Engine + Static Spec Rules (2-3 sessions)

**Create:**
- `validation/models.py`, `validation/runner.py`
- 8 static spec rules: S01, S02, S05, S06, S08, S09, S10, S11
- Test fixtures: good/bad specs
- Per-rule unit tests + runner integration test

**Copy from FM:** Nothing.

**Runnable:** `sw check --level=component good_spec.md` → all PASS

---
