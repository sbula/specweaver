# Feature 3.9 — Podman/Docker Containerization

Bundle SpecWeaver (Python + `sw` CLI + SQLite + `sw serve`) into a container image for one-command deployment. Volume-mount host project directories for file access with strict path boundaries.

> **Depends on**: Feature 3.7 (REST API), Feature 3.8 (Web Dashboard)
> **Runtime**: Podman or Docker (OCI-compatible image)

---

## Motivation

SpecWeaver currently requires a local Python environment with `uv sync --all-extras`. Containerization enables:

1. **Zero-install deployment** — run SpecWeaver on any machine with Podman/Docker installed
2. **Reproducible environment** — consistent Python version, dependencies, and SQLite
3. **Remote/server deployment** — run `sw serve` on a headless server, access the dashboard remotely
4. **CI/CD integration** — use the container image in pipelines for spec validation and code generation
5. **Team sharing** — one `podman run` command instead of "clone → install → configure"

---

## Design Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | **Path configuration** | `SPECWEAVER_DATA_DIR` env var via centralized `config/paths.py` | Explicit, no `HOME` hacks. Works for containers, CI, and custom installs. |
| 2 | **Base image** | `python:3.13-slim` (verify `tree-sitter` wheels first; fall back to multi-stage if needed) | Slim keeps image small. Pre-built `manylinux` wheels avoid build-essential. |
| 3 | **Build tool** | `uv` installed in container, `uv sync --all-extras` | Matches dev workflow. Fast, deterministic installs. |
| 4 | **Data directory** | `/data/.specweaver/` via `SPECWEAVER_DATA_DIR` | SQLite databases + logs persist in a single named volume. |
| 5 | **Project access** | Volume-mount at `/projects`, sub-dirs are projects | Users bind-mount: `-v ./my-project:/projects`. File tools enforce path boundaries. |
| 6 | **Port** | `8000` (internal default, user remaps with `-p`) | Matches `sw serve` default. Update roadmap to reflect. |
| 7 | **Entrypoint** | `docker-entrypoint.sh` → auto-registers projects → `exec uv run sw serve --host 0.0.0.0` | Handles first-run setup, signal forwarding via `exec`. |
| 8 | **API keys** | `--env-file .env` (default in docs), `-e` for quick use | Secure: not in shell history. `.env.example` included. |
| 9 | **Health check** | `HEALTHCHECK CMD curl -f http://localhost:8000/healthz` | Uses existing `/healthz` endpoint. |
| 10 | **User** | `USER 1000:1000` default, document `--user` override | Prevents root-owned files on host. |
| 11 | **CORS** | `CORS_ORIGINS` env var in `create_app()` | Secure by default (empty), opt-in `*` for remote. |
| 12 | **Registry** | `ghcr.io/sbula/specweaver` | Free for public repos, GitHub Actions integration. |
| 13 | **Image size** | Soft target ≤ 400MB | Track in CI, don't enforce as gate. |

> [!IMPORTANT]
> **CLI ↔ API symmetry**: Every path/config change to the CLI layer must also be applied to the API layer (`api/app.py`, `api/v1/pipelines.py`, `api/ui/routes.py`). Both use `Path.home()` directly today.

> [!NOTE]
> **Future IDE integration**: The entrypoint auto-registers projects under `/projects`, but future IDE plugins (VS Code, IntelliJ) will need an "Add Project" UI action that calls `POST /api/v1/projects` to register additional project paths at runtime.

---

## Proposed Changes

### Sub-phase 3.9a: Centralized Path Resolution

Refactor hardcoded `Path.home() / ".specweaver"` into a configurable module. This is a prerequisite for containerization but benefits all deployment modes.

#### [NEW] `src/specweaver/config/paths.py`
```python
"""Centralized SpecWeaver data path resolution.

Resolution order:
1. SPECWEAVER_DATA_DIR env var (containers, CI)
2. ~/.specweaver/ (default)
"""
import os
from pathlib import Path

def specweaver_root() -> Path:
    override = os.environ.get("SPECWEAVER_DATA_DIR")
    if override:
        return Path(override)
    return Path.home() / ".specweaver"

def config_db_path() -> Path:
    return specweaver_root() / "specweaver.db"

def state_db_path() -> Path:
    return specweaver_root() / "pipeline_state.db"

def logs_dir() -> Path:
    return specweaver_root() / "logs"
```

#### [MODIFY] CLI layer — replace `Path.home()` calls
- `src/specweaver/cli/_core.py` (line 34) → `config_db_path()`
- `src/specweaver/cli/serve.py` (line 56) → `config_db_path()`
- `src/specweaver/cli/pipelines.py` (line 29) → `state_db_path()`
- `src/specweaver/logging.py` (lines 34-35) → `specweaver_root()`, `logs_dir()`

#### [MODIFY] API layer — replace `Path.home()` calls (CLI ↔ API symmetry)
- `src/specweaver/api/app.py` (line 87) → `config_db_path()`
- `src/specweaver/api/v1/pipelines.py` (lines 85, 128, 169, 195, 261) → `state_db_path()`
- `src/specweaver/api/ui/routes.py` (lines 58, 74) → `state_db_path()`

#### [MODIFY] `src/specweaver/api/app.py` — CORS env var support
Add `CORS_ORIGINS` env var parsing in `create_app()`:
```python
import os
cors_env = os.environ.get("CORS_ORIGINS", "")
if cors_env:
    extra_origins = [o.strip() for o in cors_env.split(",")]
    cors_origins = (cors_origins or []) + extra_origins
```

---

### Sub-phase 3.9b: Containerfile + Compose

#### [NEW] `Containerfile`
```dockerfile
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install runtime deps (git for sw scan/GitAtom, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files (README.md needed by pyproject.toml metadata)
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

# Install with all extras (includes [serve])
RUN uv sync --all-extras --no-dev --frozen

# Create data and project directories
RUN mkdir -p /data/.specweaver /projects

# Non-root user (override with --user for custom UID)
RUN groupadd -g 1000 specweaver && useradd -u 1000 -g specweaver -m specweaver
RUN chown -R specweaver:specweaver /data /projects /app
USER 1000:1000

# Configure paths via env var (not HOME hack)
ENV SPECWEAVER_DATA_DIR=/data/.specweaver
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

COPY docker-entrypoint.sh /app/
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
```

#### [NEW] `docker-entrypoint.sh`
```bash
#!/bin/sh
set -e

# Auto-register projects under /projects if none exist
if [ -d /projects ]; then
    for dir in /projects/*/; do
        [ -d "$dir" ] || continue
        name=$(basename "$dir")
        uv run sw init "$name" --path "$dir" 2>/dev/null || true
    done
    # If no sub-dirs, register /projects itself
    if [ -z "$(ls -d /projects/*/ 2>/dev/null)" ]; then
        uv run sw init project --path /projects 2>/dev/null || true
    fi
fi

# Forward to sw command (exec replaces shell for signal handling)
exec uv run sw "$@"
```

#### [NEW] `compose.yaml`
```yaml
services:
  specweaver:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - specweaver-data:/data/.specweaver
      - ${PROJECT_DIR:-.}:/projects
    env_file:
      - .env
    restart: unless-stopped

volumes:
  specweaver-data:
```

#### [NEW] `.env.example`
```bash
# Required: Gemini API key for LLM features
GEMINI_API_KEY=

# Optional: Host project directory (for compose.yaml)
PROJECT_DIR=./my-project

# Optional: Override data directory (default: /data/.specweaver in container)
# SPECWEAVER_DATA_DIR=

# Optional: CORS origins for remote dashboard access (comma-separated)
# CORS_ORIGINS=http://192.168.1.100:8000
```

#### [NEW] `.dockerignore`
```
.git
.venv
__pycache__
*.pyc
tests/
docs/
.agents/
.ruff_cache/
.pytest_cache/
.mypy_cache/
*.egg-info
```

---

### Sub-phase 3.9c: CI/CD (GitHub Actions)

#### [NEW] `.github/workflows/container.yml`
```yaml
name: Container Image
on:
  push:
    tags: ['v*']

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Containerfile
          push: true
          tags: |
            ghcr.io/sbula/specweaver:${{ github.ref_name }}
            ghcr.io/sbula/specweaver:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

> Multi-arch (ARM/Apple Silicon) deferred to a follow-up.

---

### Sub-phase 3.9d: Documentation

#### [MODIFY] `README.md`
Add "Container Deployment" section:
```bash
# One-command deployment (Podman or Docker)
podman run --env-file .env \
  -v ./my-project:/projects \
  -p 8000:8000 \
  ghcr.io/sbula/specweaver

# Access the dashboard
open http://localhost:8000/dashboard
```

> [!NOTE]
> The data volume must be a local filesystem or named volume (not NFS/CIFS) for SQLite WAL mode compatibility.
> For non-standard UID, use `--user $(id -u):$(id -g)`.
> Podman users can use `--userns=keep-id` for automatic UID mapping.

#### [MODIFY] `docs/quickstart.md`
Add container quickstart as an alternative to the Python install flow.


Add Section 17: Containerization (path module unit tests).

#### [MODIFY] `docs/proposals/specweaver_roadmap.md` + `phase_3_feature_expansion.md`
Mark Feature 3.9 as complete with test count.

#### [MODIFY] `docs/roadmap/phase_3_feature_expansion.md`
Update roadmap port description from "8080/5001" to "8000".

---

## Verification Plan

### Automated Tests (Sub-phase 3.9a)
1. **Path module** — unit tests for `specweaver_root()`, `config_db_path()`, `state_db_path()`, `logs_dir()` with and without `SPECWEAVER_DATA_DIR`
2. **CORS env var** — test `create_app()` with `CORS_ORIGINS` set
3. **Existing suite** — all 3142+ tests must pass after the refactor (no behavioral changes)
4. **Ruff + mypy** — clean

### Container Tests (Sub-phase 3.9b)
1. `podman build -t specweaver .` completes without errors
2. `podman run -d specweaver && curl http://localhost:8000/healthz` returns `{"status": "ok"}`
3. Volume persistence: `sw init`, stop, restart, verify project exists
4. Entrypoint auto-registration: mount project dir, verify `sw projects` lists it
5. `docker stop` completes in < 3s (signal forwarding works)

### Manual Verification
1. Desktop browser: `http://localhost:8000/dashboard`
2. Remote access: set `CORS_ORIGINS=*`, access from another machine
3. `sw standards scan` works inside container (git installed)
4. Files created in `/projects` are owned by UID 1000 on host
5. Test with both Podman and Docker
