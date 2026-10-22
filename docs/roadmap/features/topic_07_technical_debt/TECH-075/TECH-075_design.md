# Design: Paths From Outside Can Leave the Project

- **Feature ID**: TECH-075
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 7 below.

## Problem Statement

A path given by an API client or an agent is not always kept inside the project: the pipeline run's
spec, the protocol tool and most QA intents accept any path, and the guard that exists is written
five ways.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **Fix first #2** — `POST /pipelines/{name}/run` joins `project_root / body.spec` with no path
  guard; `../../x` is accepted as the spec. Where: `interfaces/api/v1/pipelines.py:204`.
- **Fix first #3** — The protocol tool reads any path an agent gives it; of the QA intents only
  `run_tests` checks paths. Where: `sandbox/protocol/core/atom.py:20-24`,
  `sandbox/qa_runner/core/atom.py:196`.
- **SB-10** — Path guard five ways; protocol has none; most QA intents have none. Where:
  `security.py:81`, `filesystem/core/executor.py:380`, `execution/executor.py:200`,
  `qa_runner/core/atom.py:196`, `protocol/core/atom.py:20`.
- **SB-20** — Target handling and guards differ per intent. Where: `qa_runner/core/atom.py` (514
  lines).
- **EP-6** — No path guard on the run's spec; `selector` accepted and ignored; `new_feature`
  impossible through the API. Where: `api/v1/pipelines.py:204,205`, `schemas.py:186`.
- **FL-18** — Mention resolution and path containment scattered, with different fallbacks. Where:
  `review.py:334-430`, `reviewed_spec.py:79`, `archetype_pipelines.py:190`.
- **Real defect 6** — API project registration stores the path unresolved, relative to the server's
  working folder. Where: `interfaces/api/v1/projects.py:54`.

## Goal

Every path that comes from outside goes through one boundary check, and a path outside the project
is refused.

## Open Decisions (for the grilling, not answered here)

- What the API and the tools return for a refused path (error code and text).

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-075`. Write each fix's test
red
first.
