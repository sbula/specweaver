# C-VAL-02 — Domain Profiles

**Status**: Built; `🔧` until the user signs off. · **Feature ID**: 3.3

| | |
|---|---|
| Touches | `core/config/profiles.py` · `sw config` · `core/flow/handlers/archetype_pipelines.py` · `sw check` |
| Uses | `B-INTL-01` (an archetype's own pipeline wins over a profile) |
| Plan | [as built](C-VAL-02_implementation_plan.md) |

## What it does

A project names what kind of thing it is — `web-app`, `data-pipeline`, `library`, `microservice`,
`ml-model` — and its specs are checked by that kind's limits. The project stores only the
profile's name; the name picks `validation_spec_<profile>.yaml`, which overrides the default
pipeline's limits.

The order is the same in `sw check` and in a run's validate step: `--pipeline`, then the
archetype's own pipeline, then the profile's, then the default `[agreed 2026-10-13]`.

## Functional Requirements

| # | FR | Command | Action | Outcome |
|---|-----|---------|--------|---------|
| FR-1 | List | `sw config profiles` | SHALL list every profile with its description | the user sees the choices |
| FR-2 | Show | `sw config show-profile <name>` | SHALL list the rule limits the profile sets; an unknown name fails | the user sees what it changes |
| FR-3 | Set | `sw config set-profile <name>` | SHALL store the name for the active project; an unknown name is refused | one act sets every limit |
| FR-4 | Get | `sw config get-profile` | SHALL name the active profile, or say the defaults apply | the user sees the state |
| FR-5 | Reset | `sw config reset-profile` | SHALL remove the profile, so the default limits apply again | the choice can be undone |
| FR-6 | Applied everywhere | `sw check`, validate steps | SHALL check a spec by its own project's profile, in `sw check` and in a run, in the order above `[agreed 2026-10-13]` | one project, one set of limits |

## Accepted limits

- Under session isolation a run works in a worktree, which is not the registered project folder,
  so its profile is not found and the default limits apply (the project default DAL has the same
  limit).
- Profiles bound spec rules only; code limits come from the archetype (`B-INTL-01`).

## Live demo

With `sw config set-profile library`, a spec with 9 weasel words fails S08 with "(max: 5)" under
`sw check` and under `sw run validate_only`; after `reset-profile` it says "(max: 8)", as it does with
`--pipeline validation_spec_default`. `sw check --project B` uses B's profile while A is active.
`tests/e2e/capabilities/assurance/test_profile_applies_everywhere_e2e.py` and
`tests/e2e/capabilities/workspace/test_domain_profile_e2e.py` check this.
