# ─────────────────────────────────────────────────────────────────────────────
# Multi-stage Dockerfile — eval-py (FastAPI + Pandas + Polars + SQLAlchemy)
#
# Stage 1 «builder»
#   • Creates an isolated venv and installs ALL runtime deps via pip.
#   • Has gcc + libpq-dev to compile psycopg2 from source.
#   • Nothing from this stage leaks into the final image.
#
# Stage 2 «runtime»
#   • Starts from a clean python:3.12-slim.
#   • Copies ONLY /opt/venv from builder → no compiler, no .h files.
#   • Adds only the runtime C lib (libpq5) needed by psycopg2.
#   • Runs as non-root user «appuser» (security best-practice).
#
# Result: final image ≈ 250 MB (vs ≈ 600 MB single-stage with build tools).
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Build-time system deps:
#   gcc         → compile C extensions (psycopg2)
#   libpq-dev   → PostgreSQL client headers for psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a clean virtual environment inside the image.
# We install here so the runtime stage gets a self-contained /opt/venv.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the project metadata — pip resolves deps from pyproject.toml.
# We copy src/ separately so that dep changes don't bust the src layer.
COPY pyproject.toml .

# Install runtime deps (not dev extras).
# --no-cache-dir keeps the layer small.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Runtime-only system dep: libpq5 (psycopg2 .so links against it at runtime).
# No gcc, no headers, no apt cache.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Bring the fully-installed venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy application source (separate layer → rebuilt only when code changes)
COPY src/ ./src/

# PYTHONPATH: add /app/src so that `import eval_py` resolves the package
# inside src/eval_py/ — consistent with how `pip install -e .` works locally.
ENV PYTHONPATH=/app/src

# Security: run as a dedicated non-root user
RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose the application port (documented, not published — docker-compose does that)
EXPOSE 8010

# Uvicorn starts the ASGI app.
# Module path uses eval_py.main (not src.eval_py.main) because PYTHONPATH
# points to /app/src, making eval_py a top-level importable package.
# --host 0.0.0.0 is required inside Docker (default 127.0.0.1 is unreachable
# from outside the container).
# No --reload in production: reload polls the filesystem, wastes CPU.
CMD ["uvicorn", "eval_py.main:app", "--host", "0.0.0.0", "--port", "8010"]
