# Docker Sandbox for Alibaba Cloud Skills

This directory contains Docker configuration for running all aliyun-skills in an isolated sandbox environment.

## Quick Start

### 1. Configure Credentials

```bash
# Copy environment template
cp .env.example .env

# Edit with your credentials
vim .env
```

### 2. Choose Profile and Run

```bash
# Production runtime (minimal)
docker compose --profile runtime up -d

# Development environment (with linting tools)
docker compose --profile dev up -d

# Agent runtime (AI Agent ready)
docker compose --profile agent up -d

# Interactive shell
docker compose --profile interactive run interactive

# Run tests
docker compose --profile test run test
```

## Available Profiles

| Profile | Description | Use Case |
|---------|-------------|----------|
| `runtime` | Minimal production image | Production deployment |
| `dev` | Development with linting tools | Skill development |
| `agent` | AI Agent runtime environment | Agent integration |
| `test` | Testing and validation | CI/CD pipelines |
| `interactive` | Interactive shell access | Manual testing |

## Docker Image Targets

The Dockerfile uses multi-stage builds:

| Target | Description | Size |
|--------|-------------|------|
| `base` | Go runtime + aliyun CLI | ~400MB |
| `dev` | + Python dev tools | ~500MB |
| `runtime` | Minimal production | ~400MB |
| `agent` | + Pre-cached SDK modules | ~600MB |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | - | AccessKey ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | - | AccessKey Secret |
| `ALIBABA_CLOUD_REGION_ID` | No | `cn-hangzhou` | Default region |

## Volume Mounts

| Volume | Purpose |
|--------|---------|
| `skills-data` | Skills content storage |
| `go-cache` | Go build cache (JIT SDK) |
| `go-modcache` | Go module cache |
| `sdk-workspace` | JIT Go SDK workspace |
| `output-data` | Generated reports output |

## Common Operations

### Run CLI Command in Container

```bash
# Enter interactive container
docker compose --profile interactive run interactive

# Inside container, run aliyun commands
aliyun ecs DescribeInstances --RegionId cn-hangzhou
```

### Run Skills Validation

```bash
docker compose --profile test run test
```

### Build Custom Image

```bash
# Build specific target
docker build --target agent -t aliyun-skills:custom .

# Build with no cache
docker build --no-cache -t aliyun-skills:latest .
```

### Clean Up

```bash
# Stop all containers
docker compose down

# Remove volumes
docker compose down -v

# Remove images
docker rmi aliyun-skills:runtime aliyun-skills:dev aliyun-skills:agent
```

## Integration with Agent Frameworks

### Claude Code Integration

Mount skills directory and use in agent context:

```yaml
# In your agent configuration
volumes:
  - ./alicloud-*-ops:/skills/
environment:
  - SKILLS_HOME=/skills
  - SKILLS_RUNTIME=docker
```

### MCP Server Integration

Skills can be exposed as MCP server endpoints from the container.

## Security Considerations

1. **Credentials**: Never commit `.env` file. Use environment variables or secrets management.
2. **Read-only mounts**: Production profiles mount skills as read-only.
3. **Non-root user**: Runtime containers run as `skillsrunner` (uid 1000).
4. **No new privileges**: Security profile `no-new-privileges:true` applied.

## Troubleshooting

### CLI Not Working

```bash
# Verify CLI installation
docker compose --profile interactive run interactive -- aliyun version

# Check credentials
docker compose --profile interactive run interactive -- env | grep ALIBABA
```

### Go SDK JIT Compilation Fails

```bash
# Clear cache
docker volume rm aliyun-skills-go-cache aliyun-skills-go-modcache

# Rebuild with fresh cache
docker compose --profile agent build --no-cache
```

### Network Issues (China Region)

The image uses `GOPROXY=https://goproxy.cn,direct` for faster downloads in China.