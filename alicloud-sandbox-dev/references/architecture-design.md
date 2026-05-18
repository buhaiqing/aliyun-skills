# Architecture Design Guide

> **Purpose**: How to design the FC Sandbox Sidecar proxy architecture for Go/Python implementations.

## 1. Why Sidecar?

### Problem Statement

Java business containers calling AgentRun Sandbox APIs directly face these challenges:
- Complex ACS3-HMAC-SHA256 signing (~250 lines of Java code)
- AK/SK credential exposure risk in application memory
- Each language must re-implement signing logic
- WebSocket TTY handling in Java adds dependency complexity
- API changes require code changes in every service

### Solution: Sidecar Proxy Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                      K8s Pod / FC Container                      │
│                                                                 │
│  ┌──────────────────────┐    ┌───────────────────────────────┐  │
│  │  Java Business        │    │  Sidecar Container             │  │
│  │  Container            │    │  (Go or Python)                │  │
│  │                      │    │                               │  │
│  │  ┌────────────────┐  │    │  ┌─────────────────────────┐ │  │
│  │  │ SandboxClient   │──┼────┼─►│  HTTP/gRPC Listener      │ │  │
│  │  │ (lightweight)   │  │    │  │  (localhost:8080)       │ │  │
│  │  └────────────────┘  │    │  └─────────────────────────┘ │  │
│  │  - No AK/SK          │    │                               │  │
│  │  - No signing        │    │  ┌─────────────────────────┐ │  │
│  │  - No API awareness  │    │  │  Auth Manager            │ │  │
│  └──────────────────────┘    │  │  - AK/SK storage         │ │  │
│                              │  │  - STS token rotation    │ │  │
│                              │  │  - Signature generation  │ │  │
│                              │  └─────────────────────────┘ │  │
│                              │                               │  │
│                              │  ┌─────────────────────────┐ │  │
│                              │  │  Request Router          │ │  │
│                              │  │  - Control plane → API   │ │  │
│                              │  │  - Data plane → API      │ │  │
│                              │  │  - Multi-region routing  │ │  │
│                              │  └─────────────────────────┘ │  │
│                              │                               │  │
│                              │  ┌─────────────────────────┐ │  │
│                              │  │  Resilience Layer        │ │  │
│                              │  │  - Rate limiter          │ │  │
│                              │  │  - Circuit breaker       │ │  │
│                              │  │  - Retry (exponential)   │ │  │
│                              │  └─────────────────────────┘ │  │
│                              │                               │  │
│                              │  ┌─────────────────────────┐ │  │
│                              │  │  Observability           │ │  │
│                              │  │  - Prometheus /metrics   │ │  │
│                              │  │  - OpenTelemetry tracing │ │  │
│                              │  └─────────────────────────┘ │  │
│                              └───────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                      │
                                      │ (HTTPS with signing)
                                      ▼
                    ┌─────────────────────────────────┐
                    │  Aliyun AgentRun API             │
                    │  Control: agentrun.{region}...   │
                    │  Data: {account}.agentrun-data...│
                    └─────────────────────────────────┘
```

## 2. Deployment Mode Decision Matrix

| Factor | Sidecar (Same Pod) | Independent Deployment |
|--------|--------------------|----------------------|
| **Latency** | < 1ms (localhost/UDS) | 2-5ms (K8s network) |
| **Credential Isolation** | Same Pod Secret | Complete isolation |
| **Resource Overhead** | Per-Pod (~50MB) | Shared (1 instance → N pods) |
| **Scaling** | 1:1 with business pods | Independent scaling |
| **FC Compatibility** | Needs FC Sidecar support | ✅ Always works |
| **Recommended For** | High-frequency K8s calls | Low-frequency, FC environments |

**Decision**: For low-frequency usage + FC environment → **Independent Deployment** is recommended.

## 3. Core Module Architecture

### 3.1 Module Dependency Graph

```
                    ┌─────────────┐
                    │   main()    │
                    │   entry     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
      ┌──────────────┐ ┌──────────┐ ┌──────────────┐
      │ HTTP Server   │ │ Config   │ │ Logger       │
      │ (net/http)    │ │ (YAML)   │ │ (zap)        │
      └──────┬───────┘ └──────────┘ └──────────────┘
             │
      ┌──────┴───────┐
      │  Middleware   │
      │  Chain        │
      └──────┬───────┘
             │
    ┌────────┼────────┐
    │        │        │
    ▼        ▼        ▼
┌───────┐ ┌──────┐ ┌──────────┐
│ Auth  │ │ Rate │ │ Circuit  │
│ Signing│ │Limit │ │ Breaker  │
└───┬───┘ └──────┘ └──────────┘
    │
    ▼
┌──────────────────┐
│  Request Router  │
├──────────────────┤
│ Control Plane    │──► agentrun.{region}.aliyuncs.com
│ Data Plane       │──► {account}.agentrun-data.{region}.aliyuncs.com
│ WebSocket Proxy  │──► WS upgrade + proxy
└──────────────────┘
```

### 3.2 Module Responsibilities

| Module | Go Implementation | Python Implementation |
|--------|-------------------|----------------------|
| HTTP Server | `net/http` (stdlib) | `aiohttp` or `FastAPI` |
| Auth Manager | Custom HMAC-SHA256 | `hmac` + `hashlib` (stdlib) |
| Rate Limiter | `golang.org/x/time/rate` | `aioratelimit` |
| Circuit Breaker | `sony/gobreaker` | `circuitbreaker` |
| Config | `go-yaml/yaml` | `pyyaml` |
| Logger | `uber-go/zap` | `structlog` |
| Prometheus | `prometheus/client_golang` | `prometheus_client` |
| OTel | `go.opentelemetry.io/otel` | `opentelemetry-api` |

## 4. Communication Protocols

| Protocol | Use Case | Business-Side Interface |
|----------|----------|------------------------|
| **HTTP REST** | Control plane, simple data plane calls | `POST /api/sandbox/v1/sandboxes` |
| **WebSocket** | Interactive TTY sessions | `WS /ws/tty/{sandboxId}` |
| **Unix Domain Socket** | Same-host ultra-low-latency | `http+unix:///tmp/sandbox.sock` |

### API Design Pattern (Business → Sidecar)

```yaml
# Sidecar exposes simplified endpoints to business applications
# Business never sees: signing, region URLs, account IDs

GET  /api/sandbox/v1/templates          → GET  agentrun.{region}/.../templates
POST /api/sandbox/v1/templates          → POST agentrun.{region}/.../templates
DELETE /api/sandbox/v1/templates/:id    → DELETE agentrun.{region}/.../templates/:id

POST /api/sandbox/v1/sandboxes          → POST agentrun.{region}/.../sandboxes
POST /api/sandbox/v1/sandboxes/:id/stop → POST agentrun.{region}/.../sandboxes/:id/stop
DELETE /api/sandbox/v1/sandboxes/:id    → DELETE agentrun.{region}/.../sandboxes/:id

POST /api/sandbox/v1/sandboxes/:id/execute    → POST {account}.agentrun-data....
GET  /api/sandbox/v1/sandboxes/:id/health     → GET {account}.agentrun-data....
GET  /api/sandbox/v1/sandboxes/:id/files      → GET {account}.agentrun-data....
POST /api/sandbox/v1/sandboxes/:id/files      → POST {account}.agentrun-data....
WS   /ws/tty/:id                             → WS {account}.agentrun-data....

GET  /metrics                          → Prometheus metrics endpoint
GET  /healthz                          → Sidecar health check
```

## 5. State Synchronization Architecture

See section 3.5 of the analysis document. Key points:

- Use `ScheduledExecutorService` (Java) / `time.Ticker` (Go) / `asyncio` (Python) for polling
- Store state in `ConcurrentHashMap` (Java) / `sync.Map` (Go) / `dict + asyncio.Lock` (Python)
- Publish state changes via events (Spring Events / Go channels / Python asyncio events)
- For multi-Pod deployments, use Redis distributed locks to prevent duplicate polling

## 6. Security Considerations

1. **AK/SK must never leave the Sidecar**
2. **Use STS temporary credentials** when possible (auto-rotate every 1 hour)
3. **Encrypt sensitive data** in transit (HTTPS mandatory)
4. **Implement rate limiting** to prevent abuse
5. **Log sanitized requests** — never log Authorization headers or body content containing credentials

## 7. Technology Selection Summary

| Decision | Recommendation | Reasoning |
|----------|----------------|-----------|
| **Language** | Go | Single binary, goroutines, mature HTTP lib |
| **Deployment** | Independent Deployment (for FC) | Better compatibility, resource efficiency |
| **Protocol** | HTTP REST + WebSocket | Simple for Java clients, good WS support |
| **Signing** | Custom HMAC-SHA256 | No official AgentRun SDK exists yet |
| **State Sync** | Background ticker + event channels | Low overhead, event-driven |
