# C-VAL-02 — Domain Profiles for Threshold Calibration

**Status**: Proposal — awaiting approval (2026-03-19) · **Feature ID**: 3.3 · Plan only, no separate
design

| | |
|---|---|
| Scope | named preset bundles for validation rule overrides, CLI commands, DB storage |
| Out of scope | user-extensible YAML profiles (deferred to 3.3b); non-validation config (LLM model, temperature) |
| Source | `future_capabilities_reference.md` §19, [phase_3_feature_expansion.md](../phase_3_feature_expansion.md) |

## Goal

Domains need different validation: a web-app wants strict ambiguity checks and high coverage; an ML
training pipeline tolerates more complexity and can't easily reach 90% coverage. Today users set each
override by hand:

```bash
sw config set S05 --warn 50 --fail 80      # Day Test
sw config set S08 --warn 5 --fail 12        # Ambiguity
sw config set C04 --fail 60                 # Coverage
sw config set S03 --warn 8 --fail 12        # Stranger Test
# ... 6 more commands
```

That is tedious, error-prone and undiscoverable: users don't know which rules have domain-specific
sweet spots, and can't share a calibrated configuration across projects.

A profile is one name for a complete set of `RuleOverride` values.

## Where it plugs in

The override cascade (from [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/validation/runner.py#L127-L136)):

```
Code defaults → SpecKind presets → DB overrides → CLI --set flags
     ↑                ↑                 ↑              ↑
  Rule.__init__    get_presets()   _build_rule_kwargs()  --set S08.fail=5
```

| Component | File | Role |
|-----------|------|------|
| `RuleOverride` | [settings.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/settings.py#L36-L48) | `rule_id`, `enabled`, `warn_threshold`, `fail_threshold`, `extra_params` |
| `ValidationSettings` | [settings.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/settings.py#L51-L63) | Container: `overrides`, `get_override()`, `is_enabled()` |
| `_PRESETS` dict | [spec_kind.py](file:///c:/development/pitbula/specweaver/src/specweaver/validation/spec_kind.py#L56-L82) | `(rule_id, SpecKind) → kwargs` for kind-specific behaviour |
| `_build_rule_kwargs()` | [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/validation/runner.py#L40-L72) | Resolves DB overrides → rule constructor kwargs |
| `get_spec_rules()` | [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/validation/runner.py#L75-L145) | Merges: `{**kind_presets, **db_overrides}` |
| `set_validation_override()` | [database.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/database.py) | Per-project per-rule DB persistence |
| `sw config set/get/list/reset` | [cli.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli.py#L1055-L1094) | Individual override management |

Applying a profile writes its overrides into the DB layer through `set_validation_override()`:

```
Code defaults → SpecKind presets → DB overrides (incl. profile values) → CLI --set flags
                                       ↑
                                  set-profile web-app
                                  (writes multiple overrides at once)
```

> [!IMPORTANT]
> Profiles add **no new cascade layer**. They bulk-write the existing DB override layer. After a
> profile, `sw config set` can still fine-tune single rules on top.

## Design rules

- **Bundled overrides.** Applying a profile: (1) clears all rule overrides of the project, (2) writes
  the profile's overrides to the DB, (3) stores the profile name in the DB. A clean, predictable
  baseline; single overrides on top always work.
- **Hardcoded (phase 1).** Profiles are Python dicts in `config/profiles.py`, like `_PRESETS` in
  `spec_kind.py`: no new file format, no discovery, versioned with the code, easy to test.
  User-extensible profiles (`.specweaver/profiles/custom.yaml`) can come in 3.3b.
- **Validation only.** Profiles set rule thresholds only — not LLM model or temperature, constitution
  max-size, or log level. Cross-cutting profiles can come later.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Overwrite semantics**: `set-profile` clears existing overrides | Predictable — user always knows exactly what's set. Avoids stale overrides from a previous profile mixing with new ones. |
| 2 | **Profile name stored in DB** | `get-profile` can tell users which profile is active. Also serves as documentation. |
| 3 | **5 initial profiles**: `web-app`, `data-pipeline`, `library`, `microservice`, `ml-model` | Covers the most common project archetypes. Easy to add more later. |
| 4 | **Hardcoded Python dicts** (not YAML) | Matches `_PRESETS` pattern. No file I/O, no parser, no discovery. Quick win. |
| 5 | **`reset-profile` clears overrides + profile name** | Clean "back to defaults" mechanism. |
| 6 | **Individual overrides survive profile application** | After `set-profile`, `config set S08 --fail 3` adds/overwrites on top. User can always fine-tune. |

## Profiles

| Rule | `web-app` | `data-pipeline` | `library` | `microservice` | `ml-model` |
|------|-----------|-----------------|-----------|----------------|------------|
| **S01** (One-Sentence) | default | default | default | default | default |
| **S03** (Stranger) | w=3, f=5 | w=6, f=10 | w=2, f=4 | w=3, f=5 | w=8, f=12 |
| **S05** (Day Test) | w=30, f=50 | w=50, f=80 | w=20, f=40 | w=25, f=45 | w=80, f=120 |
| **S07** (Test-First) | default | default | w=8, f=6 (strict) | default | w=4, f=3 (lenient) |
| **S08** (Ambiguity) | w=3, f=8 | w=5, f=12 | w=2, f=5 | w=3, f=8 | w=8, f=15 |
| **S11** (Terminology) | default | default | w=2, f=4 (strict) | default | w=5, f=8 (lenient) |
| **C04** (Coverage) | f=70 | f=60 | f=85 | f=75 | f=50 |

"default" = the profile does not override that rule; code defaults apply. Profiles set only rules
where domain calibration adds value.

| Profile | Description |
|---------|-------------|
| `web-app` | Balanced thresholds for web applications. Moderate complexity, standard coverage. |
| `data-pipeline` | Lenient on complexity (ETL pipelines are naturally complex) and external references. Lower coverage bar (hard to test I/O-heavy code). |
| `library` | Strict thresholds for public-facing libraries. High coverage, low ambiguity, consistent terminology. |
| `microservice` | Similar to web-app but tuned for service boundaries. Focus on contract clarity. |
| `ml-model` | Very lenient thresholds for ML/AI projects. High complexity tolerance, low coverage bar, lenient ambiguity (research-style specs). |

## Changes

### 1. Profiles — [NEW] `src/specweaver/config/profiles.py`

```python
"""Domain profiles — named preset bundles for validation threshold calibration.

Each profile maps rule IDs to RuleOverride values. Applying a profile
bulk-writes these overrides to the project's DB, replacing any existing
overrides.
"""

from specweaver.core.config.settings import RuleOverride

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

### 2. DB: active profile — [MODIFY] `src/specweaver/config/database.py`

Schema v5 migration — `domain_profile` column on `project_settings`:

```sql
ALTER TABLE project_settings ADD COLUMN domain_profile TEXT DEFAULT NULL;
```

New methods: `set_domain_profile(project_name: str, profile_name: str | None) -> None` and
`get_domain_profile(project_name: str) -> str | None`.

`set_domain_profile()`: (1) clear all rule overrides of the project, (2) write each profile override
via `set_validation_override()`, (3) store the name in `project_settings.domain_profile`. With
`None`: clear all overrides and the profile name.

### 3. CLI — [MODIFY] `src/specweaver/cli.py`

On the existing `config_app` sub-app:

```
sw config set-profile <name>      # Apply a domain profile
sw config get-profile             # Show active profile (if any)
sw config profiles                # List all available profiles
sw config show-profile <name>     # Show what a profile would set
sw config reset-profile           # Clear profile and all overrides
```

**`set-profile` flow:** validate the name → clear all rule overrides → write the profile's overrides →
store the name → print "✓ Profile 'web-app' applied (4 rule overrides set)".

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

### 4. Runner — no change

> [!TIP]
> **`runner.py` is untouched.** Profiles write the existing DB override layer, so `_build_rule_kwargs()`
> and `get_spec_rules()` pick them up as is. That is what makes this a quick win.

## Tests

| Test File | Tests | Covers |
|-----------|-------|--------|
| `tests/unit/config/test_profiles.py` [NEW] | ~15 | `DomainProfile` model, `get_profile()`, `list_profiles()`, all 5 profiles valid, override values correct, unknown profile returns None |
| `tests/unit/config/test_database.py` [EXTEND] | ~8 | Schema v5 migration, `set_domain_profile()`, `get_domain_profile()`, set+clear round-trip, overwrites clear previous overrides |
| `tests/e2e/test_lifecycle.py` [EXTEND] | ~10 | `sw config set-profile`, `get-profile`, `profiles`, `show-profile`, `reset-profile`, invalid profile name, profile + individual override on top |
| `tests/integration/test_profile_cascade.py` [NEW] | ~8 | Profile overrides are picked up by `get_spec_rules()` and `get_code_rules()`, cascade order correct (profile < individual override), reset returns to defaults |

Expected: ~40 new tests. Regression:

```bash
uv run pytest tests/ -x -q          # All 1974+ tests must pass
uv run ruff check src/ tests/       # Zero new lint issues
```

Manual:

1. `sw config profiles` → lists 5 profiles with descriptions
2. `sw config show-profile web-app` → shows 4 rule overrides
3. `sw config set-profile web-app` → applies overrides, stored in DB
4. `sw config get-profile` → shows "web-app"
5. `sw config list` → shows the 4 overrides from the profile
6. `sw config set S08 --fail 3` → fine-tunes on top of profile
7. `sw config list` → shows 4 overrides, S08 fail now 3
8. `sw config reset-profile` → clears all overrides + profile name
9. `sw check spec.md` → uses code defaults again

## Docs to update

| Document | Update |
|----------|--------|
| `README.md` | Add Domain Profiles to Features list, add profile commands to CLI table |
| `docs/quickstart.md` | Add "Choose a domain profile" section |
| `docs/developer_guide.html` | Add profiles section, update override cascade diagram |
| `docs/roadmap/specweaver_roadmap.md` | Mark 3.3 as ✅ when complete |
| `docs/roadmap/phase_3_feature_expansion.md` | Update 3.3 entry |

## As built

Shipped (✅ in `docs/roadmap/capability_matrix.md`). **Since moved** (checked 2026-09-25): profiles
live in `src/specweaver/core/config/profiles.py`.
