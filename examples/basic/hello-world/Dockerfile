# Multi-stage Docker build for SEGA Hello World example
FROM node:18-alpine AS base

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Development stage
FROM base AS development
RUN npm ci
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# Production stage
FROM base AS production

# Create non-root user with standardized UID/GID
ARG APP_UID=1005
ARG APP_GID=1005
RUN addgroup -g ${APP_GID} -S sega
RUN adduser -S sega -u ${APP_UID} -G sega

# Copy application code
COPY --chown=sega:sega . .

# Switch to non-root user
USER sega

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', (res) => { process.exit(res.statusCode === 200 ? 0 : 1) })"

# Start application
CMD ["npm", "start"]

# Set labels
LABEL maintainer="team@example.com"
LABEL org.opencontainers.image.source="https://github.com/example/sega"
LABEL org.opencontainers.image.description="SEGA - Application service"
LABEL org.opencontainers.image.version="1.0.0"
