# D-EXEC-01 — Podman/Docker Integration: Plan

**Status**: DELIVERED — plan written 2026-08-19, after the fact · **Commit boundaries**: one,
retrospective · Design: [D-EXEC-01_design.md](D-EXEC-01_design.md)

## Goal

Record which artefact owns each requirement. The capability shipped before it had a design, so there
was no plan to schedule against; `check_fr_coverage.py` needs this to judge the ledger, and a reader
needs it to find what a requirement describes.

## CB-1 — the deployment image, as shipped

| Task | FR | Artefact |
|---|---|---|
| T1 | FR-1 | `Containerfile` — `ENTRYPOINT`, the `serve` default command, and `EXPOSE 8000`, so `podman run <image>` alone serves |
| T2 | FR-2 | `ENV SPECWEAVER_DATA_DIR=/data/.specweaver`, resolved by `core/config/paths.py`, so state is one mountable directory |
| T3 | FR-3 | `groupadd`/`useradd` and a `USER` directive placed **before** the entrypoint |
| T4 | FR-4 | `HEALTHCHECK` querying `/healthz`, so "up" and "answering" are distinguishable |
| T5 | FR-5 | `.github/workflows/container.yml`, triggered on `v*` tags, pushing to GHCR |

**T3's ordering is the requirement, not a detail.** A `USER` after `ENTRYPOINT` reads like hardening
and changes nothing — the entrypoint has already started as root. The test asserts the line order.

**No task builds the image** — a CI job (see design §Limits).
