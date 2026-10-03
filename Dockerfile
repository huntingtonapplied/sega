FROM ubuntu:22.04

WORKDIR /app

# Install basic dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy aApplication
COPY . .

# Build placeholder
RUN echo "Configure your build process here"

# Start placeholder
CMD ["echo", "Configure your start command here"]
