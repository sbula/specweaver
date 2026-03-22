# syntax=docker/dockerfile:1

# SpecWeaver container image — one-command deployment
# Build: podman build -t specweaver .
# Run:   podman run --env-file .env -v ./project:/projects -p 8000:8000 specweaver

FROM python:3.13-slim

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install runtime dependencies:
#   - git: required by sw scan / GitAtom
#   - curl: required by HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project metadata and source (README.md needed by pyproject.toml)
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

# Install with all extras (includes [serve] for FastAPI + Uvicorn)
RUN uv sync --all-extras --no-dev --frozen

# Create data and project directories
RUN mkdir -p /data/.specweaver /projects

# Non-root user (override with --user $(id -u):$(id -g) at runtime)
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
