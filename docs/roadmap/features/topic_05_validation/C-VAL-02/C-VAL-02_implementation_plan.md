# C-VAL-02 — Domain Profiles: as built

**Design**: [C-VAL-02_design.md](C-VAL-02_design.md)

| File | Holds | FRs |
|:---|:---|:---|
| `core/config/profiles.py` | the five profiles; `profile_to_pipeline_name` | FR-1, FR-2 |
| `core/config/interfaces/cli.py` | `sw config profiles`, `show-profile`, `set-profile`, `get-profile`, `reset-profile` | FR-1, FR-2, FR-3, FR-4, FR-5 |
| `workspace/store.py` | the stored name; `domain_profile_at(db, root)` | FR-3, FR-5, FR-6 |
| `workflows/pipelines/validation_spec_<profile>.yaml` | each profile's limits | FR-6 |
| `core/flow/handlers/archetype_pipelines.py` · `assurance/validation/interfaces/cli.py` | the order: pipeline, archetype, profile, default | FR-6 |
