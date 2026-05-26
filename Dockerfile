# Alibaba Cloud Skills Docker Sandbox
# Provides isolated environment for running all aliyun-skills

# Stage 1: Base runtime image with Go and common tools
FROM golang:1.24-bookworm AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    jq \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install aliyun CLI (official Go binary, no runtime dependencies)
RUN OS=$(uname -s | tr '[:upper:]' '[:lower:]') && \
    ARCH=$(uname -m) && \
    [ "$ARCH" = "x86_64" ] && ARCH="amd64" && \
    [ "$ARCH" = "aarch64" ] && ARCH="arm64" && \
    curl -fsSL "https://aliyuncli.alicdn.com/aliyun-cli-linux-latest-${ARCH}.tgz" | tar -xz -C /usr/local/bin && \
    chmod +x /usr/local/bin/aliyun

# Verify aliyun CLI installation
RUN aliyun version

# Configure Go environment for JIT SDK fallback
ENV GOPATH=/go
ENV GOCACHE=/go/cache
ENV GOMODCACHE=/go/modcache
ENV GOPROXY=https://goproxy.cn,direct

# Create working directories
WORKDIR /skills
RUN mkdir -p /skills /tmp/aliyun-sdk-workspace /tmp/go-runtime

# Stage 2: Development image with linting tools
FROM base AS dev

# Install Python-based development tools
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install markdownlint-cli2>=0.17.0

ENV PATH="/opt/venv/bin:$PATH"

# Stage 3: Production runtime image (minimal)
FROM base AS runtime

# Copy skills content
COPY . /skills/

# Create non-root user for security
RUN useradd -m -u 1000 skillsrunner && \
    chown -R skillsrunner:skillsrunner /skills /go /tmp

USER skillsrunner

# Set default environment (will be overridden by docker-compose or runtime)
ENV ALIBABA_CLOUD_REGION_ID=cn-hangzhou

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD aliyun version || exit 1

# Default entrypoint - bash shell for interactive use
ENTRYPOINT ["/bin/bash"]
CMD ["-c", "echo 'Alibaba Cloud Skills Sandbox Ready' && sleep infinity"]

# Stage 4: Agent-ready image with full capabilities
FROM runtime AS agent

# Add agent-specific configurations
ENV SKILLS_HOME=/skills
ENV SKILLS_RUNTIME=docker

# Pre-fetch common Go SDK modules for faster JIT compilation
RUN go mod download \
    github.com/alibabacloud-go/darabonba-openapi/v2/client \
    github.com/alibabacloud-go/tea/tea \
    github.com/alibabacloud-go/cms-20190101/v7/client \
    github.com/alibabacloud-go/ecs-20140526/v4/client \
    github.com/alibabacloud-go/rds-20140815/v5/client \
    github.com/alibabacloud-go/slb-20140515/v4/client \
    github.com/alibabacloud-go/vpc-20160430/v6/client \
    github.com/alibabacloud-go/ram-20150501/v3/client \
    github.com/alibabacloud-go/kms-20160120/v3/client \
    github.com/alibabacloud-go/redis-20150101/v3/client \
    github.com/alibabacloud-go/mongodb-20190301/v3/client \
    github.com/alibabacloud-go/polardb-20200202/v5/client \
    2>/dev/null || echo "SDK modules will be JIT downloaded"

# Labels for container metadata
LABEL org.opencontainers.image.title="Alibaba Cloud Skills Sandbox"
LABEL org.opencontainers.image.description="Isolated environment for running aliyun-skills with CLI and JIT Go SDK"
LABEL org.opencontainers.image.version="2.0.0"
LABEL org.opencontainers.image.vendor="Alibaba Cloud"
LABEL org.opencontainers.image.licenses="MIT"