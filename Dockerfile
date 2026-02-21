# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.13-slim-bookworm AS builder

# Install system build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files (README.md needed for package build metadata)
COPY pyproject.toml uv.lock README.md ./

# Copy vendor wheel so uv can resolve the local path dependency
COPY vendor/ vendor/

# Install dependencies using uv
# --frozen ensures reproducible builds from the lock file
# --no-dev excludes development dependencies
RUN uv sync --frozen --no-dev

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.13-slim-bookworm

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Install uv for runtime use
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Create necessary directories and set ownership for entire /app
RUN mkdir -p /app/logs /app/cache && \
    chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser app ./app

# Copy supporting files needed at runtime
COPY --chown=appuser:appuser public ./public
COPY --chown=appuser:appuser chainlit.md ./chainlit.md

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Set entrypoint to fix permissions before starting
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]