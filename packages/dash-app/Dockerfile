# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — dash-app (Dash + Plotly + Bootstrap)
#
# Multi-stage build:
#   Stage 1 «builder»: install dependencies into /opt/venv
#   Stage 2 «runtime»: clean image with only the venv + app source
#
# Build: docker build -t llmqa/dash-app:latest .
# Run:   docker run -e EVAL_API_URL=http://localhost:8010 -p 8050:8050 llmqa/dash-app:latest
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Create isolated venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only package metadata first (layer cache: deps only rebuilt if they change)
COPY pyproject.toml .

# Install runtime dependencies
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Bring the fully-installed venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy application source
COPY src/ ./src/

# PYTHONPATH so that `import dash_app` resolves src/dash_app/
ENV PYTHONPATH=/app/src

# Runtime configuration defaults (overridden by env vars or K8s configmap)
ENV EVAL_API_URL="http://localhost:8010"
ENV DASH_PORT="8050"
ENV DASH_DEBUG="false"

# Security: non-root user
RUN useradd --create-home dashuser \
 && chown -R dashuser:dashuser /app
USER dashuser

EXPOSE 8050

# Start Dash application
CMD ["python", "-m", "dash_app.main"]
