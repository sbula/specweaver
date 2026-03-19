# Feature 3.3: Domain Profiles for Threshold Calibration — Implementation Plan

> **Date**: 2026-03-19
> **Status**: Proposal — awaiting approval
> **Scope**: Named preset bundles for validation rule overrides, CLI commands, DB storage
> **Out of scope**: User-extensible YAML profiles (deferred to 3.3b), non-validation config (LLM model, temperature)
> **Source doc**: `future_capabilities_reference.md` §19, [phase_3_feature_expansion.md](../phase_3_feature_expansion.md)

---

## 1. Problem Statement

Different project domains have fundamentally different validation needs. A web-app needs strict ambiguity checking and high code coverage, while an ML model training pipeline tolerates more complexity and can't easily achieve 90% coverage. Currently, users must manually set each override one by one:

```bash
sw config set S05 --warn 50 --fail 80      # Day Test
sw config set S08 --warn 5 --fail 12        # Ambiguity
sw config set C04 --fail 60                 # Coverage
sw config set S03 --warn 8 --fail 12        # Stranger Test
# ... 6 more commands
```

This is tedious, error-prone, and undiscoverable. Users don't know which rules have domain-specific sweet spots, and there's no way to share a calibrated configuration across projects.

---

## 2. Analysis: Current Override Cascade

The validation system has a well-defined override cascade (from [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/validation/runner.py#L127-L136)):

```
Code defaults → SpecKind presets → DB overrides → CLI --set flags
     ↑                ↑                 ↑              ↑
  Rule.__init__    get_presets()   _build_rule_kwargs()  --set S08.fail=5
```

### Key existing components

| Component | File | Role |
|-----------|------|------|
| `RuleOverride` | [settings.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/settings.py#L36-L48) | `rule_id`, `enabled`, `warn_threshold`, `fail_threshold`, `extra_params` |
| `ValidationSettings` | [settings.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/settings.py#L51-L63) | Container: `overrides`, `get_override()`, `is_enabled()` |
| `_PRESETS` dict | [spec_kind.py](file:///c:/development/pitbula/specweaver/src/specweaver/validation/spec_kind.py#L56-L82) | `(rule_id, SpecKind) → kwargs` for kind-specific behaviour |
| `_build_rule_kwargs()` | [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/validation/runner.py#L40-L72) | Resolves DB overrides → rule constructor kwargs |
| `get_spec_rules()` | [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/validation/runner.py#L75-L145) | Merges: `{**kind_presets, **db_overrides}` |
| `set_validation_override()` | [database.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/database.py) | Per-project per-rule DB persistence |
| `sw config set/get/list/reset` | [cli.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli.py#L1055-L1094) | Individual override management |

### Where profiles fit

Domain profiles are a **named preset bundle** — a single name that maps to a complete set of `RuleOverride` values. Applying a profile writes those overrides to the DB using the existing `set_validation_override()` mechanism.

```
Code defaults → SpecKind presets → DB overrides (incl. profile values) → CLI --set flags
                                       ↑
                                  set-profile web-app
                                  (writes multiple overrides at once)
```

> [!IMPORTANT]
> Profiles don't add a new layer to the cascade — they're a **convenience mechanism** that bulk-writes to the existing DB override layer. After applying a profile, individual `sw config set` commands can still fine-tune specific rules on top.

---

## 3. Design Principles

### 3.1 Profiles Are Bundled Overrides

A profile is a named mapping from rule IDs to `RuleOverride` values. Applying a profile:
1. Clears all existing rule overrides for the project
2. Writes the profile's overrides to the DB
3. Stores the profile name in DB for reference

This provides a clean, predictable baseline. Individual overrides on top are always possible.

### 3.2 Hardcoded Profiles (Phase 1)

Profiles are defined as Python dicts in `config/profiles.py` — similar to `_PRESETS` in `spec_kind.py`. This is the simplest possible approach:
- No new file formats
- No file discovery logic
- Profiles are versioned with the code
- Easy to test

User-extensible profiles (`.specweaver/profiles/custom.yaml`) can be added in a future 3.3b.

### 3.3 Validation-Only

Profiles only set validation rule thresholds. They do not set:
- LLM model or temperature
- Constitution max-size
- Log level

This keeps the feature focused and simple. Cross-cutting profiles can be added later.

---

## 4. Key Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Overwrite semantics**: `set-profile` clears existing overrides | Predictable — user always knows exactly what's set. Avoids stale overrides from a previous profile mixing with new ones. |
| 2 | **Profile name stored in DB** | `get-profile` can tell users which profile is active. Also serves as documentation. |
| 3 | **5 initial profiles**: `web-app`, `data-pipeline`, `library`, `microservice`, `ml-model` | Covers the most common project archetypes. Easy to add more later. |
| 4 | **Hardcoded Python dicts** (not YAML) | Matches `_PRESETS` pattern. No file I/O, no parser, no discovery. Quick win. |
| 5 | **`reset-profile` clears overrides + profile name** | Clean "back to defaults" mechanism. |
| 6 | **Individual overrides survive profile application** | After `set-profile`, `config set S08 --fail 3` adds/overwrites on top. User can always fine-tune. |

---

## 5. Proposed Profiles

### 5.1 Profile Definitions

| Rule | `web-app` | `data-pipeline` | `library` | `microservice` | `ml-model` |
|------|-----------|-----------------|-----------|----------------|------------|
| **S01** (One-Sentence) | default | default | default | default | default |
| **S03** (Stranger) | w=3, f=5 | w=6, f=10 | w=2, f=4 | w=3, f=5 | w=8, f=12 |
| **S05** (Day Test) | w=30, f=50 | w=50, f=80 | w=20, f=40 | w=25, f=45 | w=80, f=120 |
| **S07** (Test-First) | default | default | w=8, f=6 (strict) | default | w=4, f=3 (lenient) |
| **S08** (Ambiguity) | w=3, f=8 | w=5, f=12 | w=2, f=5 | w=3, f=8 | w=8, f=15 |
| **S11** (Terminology) | default | default | w=2, f=4 (strict) | default | w=5, f=8 (lenient) |
| **C04** (Coverage) | f=70 | f=60 | f=85 | f=75 | f=50 |

> [!NOTE]
> **"default" means the profile does not override that rule** — code defaults apply. Profiles only set rules where domain-specific calibration adds value.

### 5.2 Profile Descriptions

| Profile | Description |
|---------|-------------|
| `web-app` | Balanced thresholds for web applications. Moderate complexity, standard coverage. |
| `data-pipeline` | Lenient on complexity (ETL pipelines are naturally complex) and external references. Lower coverage bar (hard to test I/O-heavy code). |
| `library` | Strict thresholds for public-facing libraries. High coverage, low ambiguity, consistent terminology. |
| `microservice` | Similar to web-app but tuned for service boundaries. Focus on contract clarity. |
| `ml-model` | Very lenient thresholds for ML/AI projects. High complexity tolerance, low coverage bar, lenient ambiguity (research-style specs). |

---

## 6. Proposed Changes

### 6.1 Profile Definitions

#### [NEW] `src/specweaver/config/profiles.py`

```python
"""Domain profiles — named preset bundles for validation threshold calibration.

Each profile maps rule IDs to RuleOverride values. Applying a profile
bulk-writes these overrides to the project's DB, replacing any existing
overrides.
"""

from specweaver.config.settings import RuleOverride

@dataclass(frozen=True)
class DomainProfile:
    """A named collection of validation overrides for a project domain."""
    name: str
    description: str
    overrides: dict[str, RuleOverride]

PROFILES: dict[str, DomainProfile] = {
    "web-app": DomainProfile(
        name="web-app",
        description="Balanced thresholds for web applications",
        overrides={
            "S03": RuleOverride(rule_id="S03", warn_threshold=3, fail_threshold=5),
            "S05": RuleOverride(rule_id="S05", warn_threshold=30, fail_threshold=50),
            "S08": RuleOverride(rule_id="S08", warn_threshold=3, fail_threshold=8),
            "C04": RuleOverride(rule_id="C04", fail_threshold=70),
        },
    ),
    # ... data-pipeline, library, microservice, ml-model
}

def get_profile(name: str) -> DomainProfile | None:
    """Get a profile by name (case-insensitive)."""

def list_profiles() -> list[DomainProfile]:
    """Return all available profiles, sorted by name."""
```

---

### 6.2 DB: Store Active Profile

#### [MODIFY] `src/specweaver/config/database.py`

Schema v5 migration — add `domain_profile` column to `project_settings`:

```sql
ALTER TABLE project_settings ADD COLUMN domain_profile TEXT DEFAULT NULL;
```

New methods:
- `set_domain_profile(project_name: str, profile_name: str | None) -> None`
- `get_domain_profile(project_name: str) -> str | None`

When `set_domain_profile()` is called:
1. Clear all existing rule overrides for the project
2. Write each override from the profile via `set_validation_override()`
3. Store the profile name in `project_settings.domain_profile`

When `None` is passed, clear all overrides and reset the profile name.

---

### 6.3 CLI Commands

#### [MODIFY] `src/specweaver/cli.py`

Add to the existing `config_app` sub-app:

```
sw config set-profile <name>      # Apply a domain profile
sw config get-profile             # Show active profile (if any)
sw config profiles                # List all available profiles
sw config show-profile <name>     # Show what a profile would set
sw config reset-profile           # Clear profile and all overrides
```

**`set-profile` flow:**
1. Validate profile name exists
2. Clear all existing rule overrides
3. Write profile overrides to DB
4. Store profile name
5. Print summary: "✓ Profile 'web-app' applied (4 rule overrides set)"

**`profiles` output:**
```
Available profiles:
  web-app          Balanced thresholds for web applications
  data-pipeline    Lenient on complexity and external references
  library          Strict thresholds for public-facing libraries
  microservice     Tuned for service boundaries and contract clarity
  ml-model         Very lenient thresholds for ML/AI projects
```

**`show-profile` output:**
```
Profile: web-app — Balanced thresholds for web applications

  S03 (Stranger Test)    warn=3  fail=5
  S05 (Day Test)         warn=30 fail=50
  S08 (Ambiguity)        warn=3  fail=8
  C04 (Coverage)                 fail=70

Rules not listed use code defaults.
```

---

### 6.4 Runner Integration (None Required)

> [!TIP]
> **No changes to `runner.py`.** Since profiles write to the existing DB override layer, the runner's `_build_rule_kwargs()` and `get_spec_rules()` already pick them up automatically. This is the key insight that makes this feature a quick win.

---

## 7. Verification Plan

### Automated Tests

| Test File | Tests | Covers |
|-----------|-------|--------|
| `tests/unit/config/test_profiles.py` [NEW] | ~15 | `DomainProfile` model, `get_profile()`, `list_profiles()`, all 5 profiles valid, override values correct, unknown profile returns None |
| `tests/unit/config/test_database.py` [EXTEND] | ~8 | Schema v5 migration, `set_domain_profile()`, `get_domain_profile()`, set+clear round-trip, overwrites clear previous overrides |
| `tests/e2e/test_lifecycle.py` [EXTEND] | ~10 | `sw config set-profile`, `get-profile`, `profiles`, `show-profile`, `reset-profile`, invalid profile name, profile + individual override on top |
| `tests/integration/test_profile_cascade.py` [NEW] | ~8 | Profile overrides are picked up by `get_spec_rules()` and `get_code_rules()`, cascade order correct (profile < individual override), reset returns to defaults |

**Expected: ~40 new tests**

### Regression

```bash
uv run pytest tests/ -x -q          # All 1974+ tests must pass
uv run ruff check src/ tests/       # Zero new lint issues
```

### Manual Verification

1. `sw config profiles` → lists 5 profiles with descriptions
2. `sw config show-profile web-app` → shows 4 rule overrides
3. `sw config set-profile web-app` → applies overrides, stored in DB
4. `sw config get-profile` → shows "web-app"
5. `sw config list` → shows the 4 overrides from the profile
6. `sw config set S08 --fail 3` → fine-tunes on top of profile
7. `sw config list` → shows 4 overrides, S08 fail now 3
8. `sw config reset-profile` → clears all overrides + profile name
9. `sw check spec.md` → uses code defaults again

---

## 8. Documentation Updates

| Document | Update |
|----------|--------|
| `README.md` | Add Domain Profiles to Features list, add profile commands to CLI table |
| `docs/quickstart.md` | Add "Choose a domain profile" section |
| `docs/developer_guide.html` | Add profiles section, update override cascade diagram |
| `docs/proposals/specweaver_roadmap.md` | Mark 3.3 as ✅ when complete |
| `docs/proposals/roadmap/phase_3_feature_expansion.md` | Update 3.3 entry |

---

## 9. Scope Estimate

| Component | Effort |
|-----------|--------|
| `config/profiles.py` (new) | Small — data definitions |
| `database.py` (v5 migration) | Small — 1 column + 2 methods |
| `cli.py` (5 commands) | Medium — follows existing patterns |
| Tests (~40 new) | Medium |
| Documentation | Small |

**Total: ~1 session** (comparable to constitution CLI work)
