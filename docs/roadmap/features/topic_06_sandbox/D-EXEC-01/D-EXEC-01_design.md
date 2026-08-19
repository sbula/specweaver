# Design: Podman/Docker Integration

- **Feature ID**: D-EXEC-01
- **Epic**: Topic 06 (Sandbox)
- **Status**: DELIVERED — design written 2026-08-19, after the fact

## Why this document exists

`D-EXEC-01` shipped with **no design document at all**. It was recorded in four lines of a topic
entry and nowhere else, which makes it invisible to `check_fr_sweep.py` by construction: the sweep
counts uncited FRs in designs that exist, and a design that does not exist has none. So a delivered
capability scored perfectly by having nothing to score.

This is the same backfill `D-SENS-01` and `E-UI-02` received on contact (`specweaver-dev` §3.2c).
The requirements below are written from **why the capability exists and what ships today**, not
invented — each names the artefact that implements it.

**It is not `B-EXEC-01`.** That capability sandboxes a QA run in an *ephemeral* container, mounting
the project read-only. This one is the *deployment* image: SpecWeaver itself, packaged, serving a
dashboard, with a host project volume-mounted in. They share a runtime and nothing else, and
conflating them is why `INT-US-09-SF01`'s hold named both for months.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | One-command deployment | Operator | runs the published image with a project mounted at `/projects` and a port published | `sw serve` answers on that port with no host Python, no checkout and no install step |
| FR-2 | State lives outside the image | The container | resolves every data path through `SPECWEAVER_DATA_DIR`, set to `/data/.specweaver` | state is one mountable directory rather than scattered under a home directory, so a container can be replaced without losing it |
| FR-3 | The image does not run as root | The container | creates and switches to an unprivileged user before the entrypoint | a volume-mounted host project is touched by an ordinary uid, and `--user $(id -u):$(id -g)` remains available for host-uid parity |
| FR-4 | The container reports whether it is serving | Orchestrator | polls the declared healthcheck | "the process is up" and "the API answers" are distinguishable, which a bare process check cannot do |
| FR-5 | The published image is built from a tag | CI | builds and pushes to GHCR on a `v*` tag | what is published corresponds to a released commit rather than to whatever was last pushed |

## Verifiable Proof

| FR | Test |
|---|---|
| FR-1 | `tests/integration/sandbox/execution/test_deployment_image_contract.py` — the entrypoint, the default command, and the exposed port |
| FR-2 | the same file, and `tests/unit/core/config/test_paths.py`, which pins the `SPECWEAVER_DATA_DIR` override the image relies on |
| FR-3 | the same file — a `USER` directive that is not root, declared before the entrypoint |
| FR-4 | the same file — a `HEALTHCHECK` that queries the served endpoint rather than the process |
| FR-5 | the same file — the workflow triggers on `v*` tags and pushes to `ghcr.io` |

## What is knowingly not covered

**No test builds the image.** A real build pulls a base image, installs apt packages and resolves the
full dependency set; that is a CI job, not a suite that runs on every commit. What is asserted is the
**contract the image declares** — the directives an operator depends on — so a change that silently
drops the non-root user or the healthcheck fails here rather than in production.

**The volume boundary is `E-EXEC-01`'s.** `WorkspaceBoundary` enforces that a mounted project cannot
be escaped; this capability mounts it, and does not re-implement the check.
