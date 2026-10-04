FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI + compose plugin (static, no daemon): the dashboard's action layer
# shells out to `docker compose -f <project compose> up/stop/restart` against the
# mounted /var/run/docker.sock.
RUN set -eux; \
    arch="$(uname -m)"; \
    case "$arch" in aarch64|arm64) darch=aarch64 ;; x86_64) darch=x86_64 ;; *) darch="$arch" ;; esac; \
    curl -fsSL "https://download.docker.com/linux/static/stable/${darch}/docker-27.3.1.tgz" \
      | tar xz --strip-components=1 -C /usr/local/bin docker/docker; \
    mkdir -p /usr/local/lib/docker/cli-plugins; \
    curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-${darch}" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose; \
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose; \
    docker --version && docker compose version

# Copy project files
COPY sega/engine/pyproject.toml ./
COPY sega/README.md /README.md
COPY sega/engine/sega/ ./sega/

# Install SEGA
RUN pip install --no-cache-dir -e ".[dashboard]"

# Create non-root user with standardized UID/GID
ARG APP_UID=5000
ARG APP_GID=5000
RUN groupadd -r -g ${APP_GID} sega && \
    useradd -r -u ${APP_UID} -g sega -m -d /home/sega -s /bin/bash sega && \
    mkdir -p /var/log/sega && \
    chown -R sega:sega /app /home/sega /var/log/sega
USER sega

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the SEGA API server
CMD ["uvicorn", "sega.api.server:app", "--host", "0.0.0.0", "--port", "8000"]

# Set labels
LABEL maintainer="team@example.com"
LABEL org.opencontainers.image.source="https://gitlab.com/example-org-group/sega"
LABEL org.opencontainers.image.description="SEGA - Scalable Engineering & Growth Automation"
LABEL org.opencontainers.image.version="1.0.0"