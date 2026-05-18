---
name: alicloud-sandbox-dev
description: >-
  Use this skill to develop FC Sandbox Sidecar proxy applications that mediate
  between Java business containers and Alibaba Cloud AgentRun Sandbox APIs.
  Covers Code Interpreter, BrowserTool, AIO Sandbox, and Deep Hibernation
  integration. Supports Go and Python implementations. Handles ACS3-HMAC-SHA256
  signing, credential management, WebSocket TTY, state synchronization, and
  observability. Reach for this skill when the user needs to "build a sandbox
  proxy", "develop a sidecar for AgentRun", "integrate Code Interpreter",
  "implement sandbox signing", "create a sandbox-sidecar", or "add sandbox
  support to our Java service". Keywords: FC Sandbox, Code Interpreter,
  AgentRun, Sidecar, proxy, signing, sandbox, 沙箱, 代码解释器, 代理,
  BrowserTool, AIO Sandbox, 深休眠, WebSocket TTY.
  Do NOT use for direct Java SDK integration (use documented patterns instead),
  ECS/RDS/other cloud product operations, or Kubernetes infrastructure management.
license: MIT
compatibility: >-
  Go 1.21+ (for Go Sidecar implementation) OR Python 3.9+ (for Python Sidecar),
  valid Alibaba Cloud API credentials (AK/SK or STS), network access to
  AgentRun API endpoints (agentrun.{region}.aliyuncs.com for control plane,
  {account}.agentrun-data.{region}.aliyuncs.com for data plane).
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-18"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  python_version_minimum: "3.9"
  api_profile: "AgentRun 2025-09-10 / https://help.aliyun.com/zh/functioncompute/fc/sandbox-function"
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
    - ALIBABA_CLOUD_ACCOUNT_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud FC Sandbox Sidecar Development Skill

## Overview

This skill is a **development runbook** for building FC Sandbox Sidecar proxy applications. The Sidecar acts as a mediator between Java business containers and Alibaba Cloud AgentRun Sandbox APIs, handling authentication, signing, request routing, and observability — so the Java application never needs to hold AK/SK or implement complex signing logic.

The skill covers the full Sandbox ecosystem: **Code Interpreter**, **BrowserTool**, **AIO Sandbox**, and **Deep Hibernation**.

### Execution Mode: API/SDK Development (NOT CLI)

**This skill operates in API/SDK development mode, NOT `cli-first` mode.**

| | `alicloud-ecs-ops` (typical) | `alicloud-sandbox-dev` |
|---|---|---|
| Execution mode | `cli_applicability: cli-first` | **API/SDK development** |
| Agent behavior | Executes `aliyun ecs` CLI commands | **Generates Go/Python Sidecar source code** |
| Alibaba Cloud support | `aliyun` CLI fully supports ECS | AgentRun has **no official CLI or SDK** — HTTP API only |
| Agent output | Operational results (instance status, etc.) | Sidecar application code files |

The skill guides the Agent to generate Go/Python source files that call AgentRun APIs via raw HTTP + ACS3-HMAC-SHA256 signing. There is **no `aliyun agentrun ...` CLI command** and **no official Java/Go/Python SDK** for AgentRun.

### Quick Start

```
不知道从哪里开始？→ 查看 [Prompt Examples](references/prompt-examples.md)，里面有 60+ 条自然语言提示词示例，
覆盖模板管理、实例管理、数据面功能、签名实现、WebSocket TTY、可观测性和端到端开发场景，
复制即用。
```

### Architecture Context

The Sidecar proxy pattern isolates credential management and API complexity from the business application:

```
Java Business Pod ──HTTP/gRPC──► Sidecar Proxy ──HTTPS (signed)──► AgentRun API
  (no AK/SK)                    (holds AK/SK)                     (control + data planes)
```

See [references/architecture-design.md](references/architecture-design.md) for complete architecture details.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User wants to develop a **Sidecar proxy** for FC Sandbox / AgentRun APIs
- Task involves implementing **ACS3-HMAC-SHA256 signing** for Sandbox API calls
- Task involves **Code Interpreter** integration (code execution, file management, TTY)
- Task involves **BrowserTool** or **AIO Sandbox** integration
- Task involves **WebSocket TTY** implementation for interactive terminal
- Task involves **sandbox state synchronization** with background threads
- Task involves **credential management** (AK/SK rotation, STS tokens)
- Task involves building **observability** for Sandbox proxy (Prometheus, OpenTelemetry)
- User asks for **Go or Python** Sidecar implementation patterns
- Keywords: Sidecar, proxy, signing, Code Interpreter, AgentRun, sandbox, BrowserTool, AIO Sandbox, TTY, WebSocket, credential rotation, state sync, 沙箱, 代码解释器, 代理, 签名

### SHOULD NOT Use This Skill When

- Task is direct Java SDK integration → reference Section 3 of [.sandbox-analysis/01-overview-comparison.md](../.sandbox-analysis/01-overview-comparison.md) for CommonRequest patterns
- Task is ECS/RDS/other cloud product operations → use respective `alicloud-*-ops` skills
- Task is Kubernetes infrastructure management → delegate to: `alicloud-ack-ops`
- Task is RAM permission management → delegate to: `alicloud-ram-ops`
- User needs **operational execution** against Sandbox APIs → this skill is for **development**, not runtime execution

### Delegation Rules

| Task | Delegate To |
|------|-------------|
| Go HTTP server implementation | Use [references/go-implementation.md](references/go-implementation.md) |
| Python HTTP server implementation | Use [references/python-implementation.md](references/python-implementation.md) |
| ACS3-HMAC-SHA256 signing algorithm | Use [references/auth-signing.md](references/auth-signing.md) |
| WebSocket TTY implementation | Use [references/websocket-tty.md](references/websocket-tty.md) |
| Prometheus metrics setup | Use [references/observability.md](references/observability.md) |
| K8s deployment configuration | Use [references/deployment-guide.md](references/deployment-guide.md) |
| Complete API reference | Use [references/api-reference.md](references/api-reference.md) |

## Placeholders

| Placeholder | Source | Description |
|-------------|--------|-------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Environment | Alibaba Cloud AccessKey ID |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Environment | Alibaba Cloud AccessKey Secret |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Environment | Region ID (e.g., `cn-hangzhou`) |
| `{{env.ALIBABA_CLOUD_ACCOUNT_ID}}` | Environment | Main account ID (for data plane URLs) |
| `{{user.sandbox_type}}` | User input | Sandbox type: `code-interpreter`, `browser-tool`, `aio-sandbox` |
| `{{user.language}}` | User input | Implementation language: `go` or `python` |
| `{{user.deployment_mode}}` | User input | Deployment: `sidecar`, `deployment`, `daemonset` |
| `{{output.sandbox_id}}` | API response | Created Sandbox instance ID |
| `{{output.template_id}}` | API response | Created template ID |

## Pre-flight Checklist

Before starting development:

1. [ ] Alibaba Cloud account with **AgentRun service** enabled
2. [ ] AK/SK credentials with **AgentRun API permissions**
3. [ ] Go 1.21+ or Python 3.9+ development environment
4. [ ] K8s cluster or FC environment for deployment testing
5. [ ] Read [references/architecture-design.md](references/architecture-design.md) for architecture understanding

## Development Workflow

### Phase 1: Architecture Design

1. Read [references/architecture-design.md](references/architecture-design.md)
2. Decide on deployment mode (Sidecar vs independent Deployment)
3. Choose implementation language (Go recommended, Python for prototyping)
4. Design API abstraction layer for business consumers

### Phase 2: Core Implementation

1. Read the language-specific guide:
   - **Go**: [references/go-implementation.md](references/go-implementation.md)
   - **Python**: [references/python-implementation.md](references/python-implementation.md)
2. Implement Auth Manager with ACS3-HMAC-256 signing (see [references/auth-signing.md](references/auth-signing.md))
3. Implement Request Router for control/data plane routing
4. Implement Resilience Layer (rate limiting, circuit breaker, retry)

### Phase 3: Advanced Features

1. Implement WebSocket TTY support (see [references/websocket-tty.md](references/websocket-tty.md))
2. Add observability (see [references/observability.md](references/observability.md))
3. Implement state synchronization with background goroutines/threads

### Phase 4: Testing & Deployment

1. Test with Sandbox API in staging environment
2. Configure resource limits and idle timeouts
3. Deploy using patterns in [references/deployment-guide.md](references/deployment-guide.md)

## API Quick Reference

### Control Plane Endpoints

| API | Method | Endpoint | Purpose |
|-----|--------|----------|---------|
| CreateTemplate | POST | `agentrun.{region}.aliyuncs.com/2025-09-10/templates` | Create sandbox template |
| GetTemplate | GET | `agentrun.{region}.aliyuncs.com/2025-09-10/templates/{templateName}` | Get template details |
| ListTemplates | GET | `agentrun.{region}.aliyuncs.com/2025-09-10/templates` | List all templates (paginated) |
| UpdateTemplate | PUT | `agentrun.{region}.aliyuncs.com/2025-09-10/templates/{templateName}` | Update template config |
| DeleteTemplate | DELETE | `agentrun.{region}.aliyuncs.com/2025-09-10/templates/{templateName}` | Delete template |
| StopTemplateMCP | PATCH | `agentrun.{region}.aliyuncs.com/2025-09-10/templates/{templateName}/mcp/stop` | Stop MCP service |
| ActivateTemplateMCP | PATCH | `agentrun.{region}.aliyuncs.com/2025-09-10/templates/{templateName}/mcp/activate` | Enable MCP service |
| CreateSandbox | POST | `agentrun.{region}.aliyuncs.com/2025-09-10/sandboxes` | Create sandbox instance |
| GetSandbox | GET | `agentrun.{region}.aliyuncs.com/2025-09-10/sandboxes/{sandboxId}` | Get sandbox details |
| ListSandboxes | GET | `agentrun.{region}.aliyuncs.com/2025-09-10/sandboxes` | List all sandboxes (paginated) |
| StopSandbox | POST | `agentrun.{region}.aliyuncs.com/2025-09-10/sandboxes/{sandboxId}/stop` | Stop sandbox |
| DeleteSandbox | DELETE | `agentrun.{region}.aliyuncs.com/2025-09-10/sandboxes/{sandboxId}` | Delete sandbox |

### Data Plane Endpoints

| API | Method | Endpoint | Purpose |
|-----|--------|----------|---------|
| Execute Code | POST | `{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/contexts/execute` | Execute code |
| Health Check | GET | `{account}.agentrun-data.{region}.aliyuncs.com/sandboxes/{sandboxId}/health` | Check sandbox health |
| File Read | GET | `.../sandboxes/{sandboxId}/files?path=...` | Read file content |
| File Write | POST | `.../sandboxes/{sandboxId}/files` | Write file content |
| TTY WebSocket | WS | `.../sandboxes/{sandboxId}/processes/tty` | Interactive terminal |

Full API details: [references/api-reference.md](references/api-reference.md)

## Critical Constraints

### Sandbox Lifecycle Limits

| Constraint | Value | Configurable? |
|------------|-------|---------------|
| Maximum hard lifecycle | **6 hours** | ❌ No |
| Idle timeout (`sandboxIdleTimeoutInSeconds`) | User-defined | ✅ Yes (recommended < 21600) |
| Maximum file upload | 100 MB | ❌ No |
| Code execution timeout | 30 seconds (max) | ✅ Yes (per call) |

**原文引用**:
> 一个沙箱实例最长生命周期为 6 小时。此外，通过 `sandboxIdleTimeoutInSeconds` 参数，可以设定一个超时时长。如果会话的浅休眠（原闲置）时间超过该值，它将被提前终止，而无需等待 6 小时的生命周期结束。
>
> — [Code Interpreter 文档 > 使用说明](https://help.aliyun.com/zh/functioncompute/fc/sandbox-sandbox-code-interepreter)

### State Machine

```
CREATING ──► READY ──(idle timeout / 6h hard limit / StopSandbox)──► TERMINATED
```

## Safety Gates

### Destructive Operations

The following operations require explicit confirmation before execution:

| Operation | Impact | Confirmation Required |
|-----------|--------|----------------------|
| `DeleteSandbox` | **Permanent loss** of sandbox state, files, and contexts | Yes — confirm sandboxId matches |
| `DeleteTemplate` | **Cannot create** new sandboxes from this template | Yes — confirm templateId and check for dependents |
| `filesystem/remove` | **Deletes** files/directories in sandbox | Verify path is not `/` or critical system path |

### Credential Security

- **NEVER** log AK/SK values, even in development
- **NEVER** pass AK/SK to business application containers
- **DO** use environment variables or K8s Secrets for credential injection
- **DO** implement credential rotation with STS temporary credentials when possible

## Response Fields

### Sandbox Instance Response

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `sandboxId` | string | API | Unique sandbox instance ID (ULID format) |
| `templateId` | string | API | Associated template ID |
| `templateName` | string | API | Template name |
| `status` | enum | API | `CREATING` \| `READY` \| `TERMINATED` |
| `sandboxIdleTimeoutInSeconds` | int | API | Configured idle timeout |
| `createdAt` | timestamp | API | Creation time (ISO 8601) |
| `lastUpdatedAt` | timestamp | API | Last update time |
| `endedAt` | timestamp | API | Termination time (only when TERMINATED) |

### Code Execution Response

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `results` | array | API | Execution result items |
| `results[].type` | string | API | `stdout`, `stderr`, `result`, `endOfExecution` |
| `results[].text` | string | API | Output content |
| `results[].status` | string | API | `ok`, `error`, `timeout` |
| `contextId` | string | API | Associated context ID |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-18 | Initial release — FC Sandbox Sidecar development skill |
