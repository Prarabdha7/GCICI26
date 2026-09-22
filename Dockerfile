# ============================================================================
# Dockerfile — JA Assure AI Marketing System
#
# Multi-stage build:
#   builder  — installs Python wheels into a virtualenv under /opt/venv.
#              Uses a full python:3.12-slim base so gcc is available to
#              compile wheels that lack a pre-built binary (e.g. psycopg).
#
#   runtime  — copies only the virtualenv and the application source from
#              the builder stage.  The runtime image has no compiler, no
#              pip, and no build-time headers, minimising attack surface
#              and final image size.
#
# FFmpeg is installed in the runtime stage from the Debian apt repository
# because it is a runtime dependency of the media assembly pipeline and
# cannot be bundled as a Python wheel.
#
# The container does not run as root: a non-privileged user 'appuser' (UID
# 1000) owns the working directory and is the entry-point executor.
#
# Build:
#   docker build -t ja-assure .
#
# Run (minimum required variable — others default to empty / fallback mode):
#   docker run -e GEMINI_API_KEY=your_key -p 8000:8000 ja-assure
# ============================================================================

# ---- stage 1: builder -------------------------------------------------------
FROM python:3.12-slim AS builder

# Prevent Python from writing .pyc files to disk during the build; they
# are created on first import in the runtime container anyway.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Copy only the requirements file first so Docker layer caching reuses the
# pip install layer on subsequent builds when only application code changes.
COPY requirements.txt .

# Create an isolated virtualenv and install all wheels into it.
# --no-cache-dir keeps the image layer lean by preventing pip from storing
# the downloaded wheel cache inside the image.
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip --no-cache-dir && \
    /opt/venv/bin/pip install -r requirements.txt --no-cache-dir


# ---- stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Prepend the virtualenv so all python and entry-point invocations resolve
    # from /opt/venv without needing 'source activate' in the entry point.
    PATH="/opt/venv/bin:$PATH"

# FFmpeg: required by assembly.py's subprocess FFmpeg path.
# libgomp1: required by some Pillow SIMD acceleration paths on ARM64.
# Both packages are kept minimal — no recommended extras installed.
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# Copy the installed virtualenv from the builder — this is the only layer
# from stage 1 that enters the runtime image.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy application source.  The .dockerignore file (sibling to this
# Dockerfile) excludes .env, *.db, temp/, assets/generated/, __pycache__/,
# and other non-essential paths.
COPY . .

# Create a non-root user for the process.  UID 1000 matches the default
# UID of most Linux developer accounts, which matters when bind-mounting
# the working directory during local development.
RUN useradd --uid 1000 --no-create-home --shell /bin/false appuser && \
    chown -R appuser:appuser /app

# Initialise the SQLite schema at build time so the container starts with
# a valid (empty) database rather than failing on first request.
# This runs as root before the USER switch so /app is writable.
RUN python -m scripts.init_db

USER appuser

# Port 8000 is the default in Settings.app_port.  Override with the
# APP_PORT environment variable to match your deployment target.
EXPOSE 8000

# Health check: hits the /health endpoint that run.py exposes.
# --interval: check every 30 seconds after startup.
# --timeout:  fail the check if the response takes more than 5 seconds.
# --start-period: give the server 10 seconds to warm up before the first check.
# --retries: mark the container unhealthy after 3 consecutive failures.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Use exec form so SIGTERM from the container runtime reaches uvicorn directly
# rather than being swallowed by a shell wrapper, enabling graceful shutdown.
CMD ["python", "run.py"]
