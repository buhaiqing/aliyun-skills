# FC 3.0 — Core Concepts

## Architecture

Function Compute (FC) is Alibaba Cloud's fully managed, event-driven, serverless compute platform. FC 3.0 simplifies the resource model compared to FC 2.0:

**FC 3.0 Resource Hierarchy:**
```
Account/Region → Function → [Versions, Aliases, Triggers, Tags]
                → VpcBindings
                → ProvisionConfigs (per qualifier)
                → AsyncConfigs (per qualifier)
                → ConcurrencyConfigs (per function)
                → ScalingConfigs
                → Sessions (stateful)
```

In FC 3.0, functions are **top-level** resources — no more service wrapping layer. Functions accept requests directly via HTTP triggers or event sources.

## Resource Model

| Entity | Description | Key Constraints |
|--------|-------------|-----------------|
| **Function** | The deployable unit — code entry point, runtime, memory, timeout | Name: 1-64 chars, alphanumeric/hyphen/underscore |
| **Version** | Immutable snapshot of function config + code | Cannot be modified after publish |
| **Alias** | Mutable pointer to a version (e.g., `prod` → `v3`) | Used for traffic splitting and gray releases |
| **Trigger** | Event source that invokes the function | Types: HTTP, OSS, Timer, Log, MNS, EventBridge, CDN |
| **ProvisionConfig** | Pre-warmed instances to eliminate cold start | Per qualifier; billed regardless of invocations |
| **ConcurrencyConfig** | Per-function concurrency limits | Reserved + max concurrency per function |
| **AsyncConfig** | Retry policy and failure destinations for async invokes | maxRetryAttempts: 0-3; maxAsyncEventAgeInSeconds: 0-259200 |
| **ScalingConfig** | Elastic scaling thresholds | CPU, memory, custom metrics |
| **Session** | Stateful session with affinity (FC 3.0 new) | SessionID binding with TTL and idle timeout |
| **VpcBinding** | Network isolation — function accesses VPC resources | Requires vSwitch and security group |
| **Layer** | Shared code library attached to functions | Reduces deployment package size |

## Limits and Quotas

| Resource | Default Limit | Adjustable |
|----------|--------------|------------|
| Functions per account per region | 100 | Yes (ticket) |
| Concurrent executions per account | 300 | Yes (ticket) |
| Function memory | 128 MB – 3072 MB (step 64 MB) | Fixed range |
| Function timeout | 1 second – 86400 seconds (24h) | Fixed range |
| Code package size (direct upload) | 50 MB | Fixed |
| Code package size (via OSS) | 500 MB | Fixed |
| Ephemeral disk | 512 MB (default) or 10240 MB | Toggle |
| Environment variables per function | 128 | Yes |
| Tags per function | 20 | Yes |

## Supported Runtimes

| Category | Runtime Identifiers |
|----------|-------------------|
| Python | python3.9, python3.10, python3.12 |
| Node.js | nodejs16, nodejs18, nodejs20 |
| Java | java8, java11, java17, java21 |
| Go | custom (compile to binary), custom-container |
| PHP | php8.2 |
| Custom | custom, custom-container (Docker image) |
| GPU | custom-container (with GPU base images) — see [gpu-inference.md](gpu-inference.md) |

### GPU Functions (LLM / vLLM / Batch)

GPU workloads use a separate **GPU function** resource type (not CPU runtimes above):

| Aspect | Detail |
|--------|--------|
| Runtime | `custom-container` only; image must expose an HTTP server |
| vLLM | Managed via **Function AI Model Service**, or self-hosted in GPU function container |
| Batching | **In-process**: vLLM continuous batching; **Cross-instance**: FC elastic scaling |
| Instance modes | Elastic (pay-per-use) or resident (prepaid pool); **cannot switch after create** |
| Ops guide | [gpu-inference.md](gpu-inference.md) — scenarios, concurrency, warmup, LLM metrics |

## Billing Model

FC 3.0 charges:
1. **Invocation count**: per request (free tier: first 1M requests/month)
2. **Resource usage (GB-s)**: memory (GB) × execution duration (seconds) (free tier: 400,000 GB-s/month)
3. **Provisioned instances**: per instance-hour, regardless of invocations
4. **Network traffic**: outbound data transfer (inbound is free)

**Cost optimization lever:** Memory allocation directly affects GB-s cost. Higher memory = faster execution (more CPU) = potentially lower total cost for CPU-intensive workloads. See [well-architected-assessment.md](well-architected-assessment.md#23-成本支柱-cost).

## Dependency Graph

```
┌─────────────────────────────────────────┐
│              FC Function                │
│  ┌─────────────┐  ┌──────────────────┐ │
│  │   Trigger   │──│    Code Package  │ │
│  └──────┬──────┘  └────────┬─────────┘ │
│         │                  │           │
│         ▼                  ▼           │
│  ┌─────────────┐  ┌──────────────────┐ │
│  │ Invocation  │──│    Runtime       │ │
│  └──────┬──────┘  └────────┬─────────┘ │
│         │                  │           │
│         ▼                  ▼           │
│  ┌─────────────┐  ┌──────────────────┐ │
│  │  Concurrency│  │    Layers        │ │
│  └──────┬──────┘  └────────┬─────────┘ │
│         │                  │           │
│         ▼                  ▼           │
│  ┌──────────────────────────────────┐  │
│  │         External Resources       │  │
│  │  (RDS, Redis, OSS, SLS, SAE...) │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Single Point of Failure Analysis

FC is inherently multi-AZ — Alibaba Cloud manages instance distribution across zones within a region. However:

| Risk | Mitigation |
|------|-----------|
| Single region deployment | Deploy critical functions in multiple regions + cross-region triggers |
| Code package unavailable (OSS) | Ensure OSS bucket is in same region; enable versioning |
| VPC dependency | Use VPC endpoints; monitor vSwitch IP availability |
| External service failure | Implement retry logic; use async with DLQ for durability |

## Cold Start Mechanics

| Factor | Impact | Mitigation |
|--------|--------|-----------|
| Package size | Larger = longer init | Use layers; minimize dependencies |
| Runtime | Java/Node.js warm up faster than Python/C++ | Choose appropriate runtime |
| VPC binding | Adds ~200-300ms for ENI setup | Pre-warm with provisioned instances |
| Layers | Additional download time | Use fewer, smaller layers |
| Memory allocation | More memory = faster init | Increase memory for latency-sensitive |
| Provisioned instances | Eliminates cold start | Configure for latency-critical functions |
| GPU + LLM model load | 10–30s+ E2E cold start | Initializer warmup, NAS weights, `min instances≥1`; see [gpu-inference.md](gpu-inference.md) |