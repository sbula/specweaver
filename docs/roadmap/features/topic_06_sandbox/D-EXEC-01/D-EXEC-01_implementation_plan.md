# Implementation Plan: D-EXEC-01

- **Feature ID**: D-EXEC-01
- **Status**: DELIVERED — plan written 2026-08-19, after the fact
- **Commit boundaries**: one, retrospective

## Why this plan is retrospective

The capability shipped before it had a design, so there was no plan to schedule against. This records
which artefact owns each requirement, which is what `check_fr_coverage.py` needs in order to judge
the ledger at all — and what a reader needs in order to find the thing a requirement describes.

## CB-1 — the deployment image, as shipped

| Task | FR | Artefact |
|---|---|---|
| T1 | FR-1 | `Containerfile` — `ENTRYPOINT`, the `serve` default command, and `EXPOSE 8000`, so `podman run <image>` alone serves |
| T2 | FR-2 | `ENV SPECWEAVER_DATA_DIR=/data/.specweaver`, resolved by `core/config/paths.py`, so state is one mountable directory |
| T3 | FR-3 | `groupadd`/`useradd` and a `USER` directive placed **before** the entrypoint |
| T4 | FR-4 | `HEALTHCHECK` querying `/healthz`, so "up" and "answering" are distinguishable |
| T5 | FR-5 | `.github/workflows/container.yml`, triggered on `v*` tags, pushing to GHCR |

**T3's ordering is the requirement, not a detail.** A `USER` after `ENTRYPOINT` reads like
hardening and changes nothing — the entrypoint has already started as root. The test asserts the
line order for that reason.

**No task builds the image.** That is a CI job: a real build pulls a base image, installs apt
packages and resolves the whole dependency set. What is owned here is the contract the image
declares, so a change that silently drops the non-root user or the healthcheck fails on commit
rather than in production.
