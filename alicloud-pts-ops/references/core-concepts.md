# Core Concepts — PTS (Performance Testing)

> Version: 1.0.0 | Last Updated: 2026-06-16

## Architecture

PTS orchestrates distributed load generators (agents) that execute HTTP/API or JMeter scripts against target endpoints.

```
┌─────────────────────────────────────────────────────────────┐
│                    PTS Control Plane                         │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │  PTS Scene   │──│ LoadConfig  │──│ RelationList     │   │
│  │  (压测场景)   │  │ (施压配置)   │  │ (链路/API列表)    │   │
│  └──────┬───────┘  └─────────────┘  └──────────────────┘   │
│         │                                                    │
│  ┌──────┴───────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │ Debug Run    │  │ Full Test   │  │ Report / Baseline│   │
│  └──────────────┘  └─────────────┘  └──────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS / VPC
                    ┌──────┴──────┐
                    │ Target SUT  │  (ECS, SLB, API Gateway, FC, …)
                    └─────────────┘
```

### Resource Types

| Resource | Description |
|----------|-------------|
| **PTS Scene** | Native PTS scene with `RelationList` + `LoadConfig` |
| **Open JMeter Scene** | JMeter script hosted on PTS |
| **JMeter Environment** | Env vars / files for JMeter runs |
| **Report** | Output of a completed or running test |
| **Baseline** | Reference metrics for regression comparison |

## Scene State Machine

```
Draft → WaitStart → Debugging → WaitStart
                ↓
            Running → Finished
                ↓
            (stop) → WaitStart
```

| Status | Meaning | Agent Action |
|--------|---------|--------------|
| `Draft` | Editable, not runnable | Save before start |
| `WaitStart` | Ready to start | OK to debug/start |
| `Debugging` | Single-thread debug | Poll status |
| `Running` | Full load test active | Monitor; stop if needed |
| `Finished` | Last run completed | Fetch report |

## Scene JSON Model (Simplified)

Key fields for `create-pts-scene` / `save-pts-scene`:

| Field | Type | Description |
|-------|------|-------------|
| `sceneName` | string | Display name |
| `loadConfig.agentCount` | int | Concurrent agent machines |
| `loadConfig.maxRunningTime` | int | Max duration (minutes) |
| `loadConfig.testMode` | string | `tps_mode` or `concurrency_mode` |
| `loadConfig.configuration.allRpsBegin` | int | Starting RPS |
| `loadConfig.configuration.allRpsLimit` | int | Peak RPS cap |
| `relationList[].apiList[].url` | string | Target URL |
| `relationList[].apiList[].method` | string | HTTP method |

> Full schema: OpenAPI `Scene` entity — [api-sdk-usage.md](api-sdk-usage.md).

## Limits & Quotas

Query quotas via [PTS quota center](https://quotas.console.aliyun.com/products/pts/quotas) or account console.

| Resource | Typical Constraint | Notes |
|----------|-------------------|-------|
| Concurrent scenes | Per account/region | Stop idle runs |
| Max agents per scene | Plan-dependent | Reduce `agentCount` on error |
| Max RPS | Plan + target capacity | Ramp gradually |
| Scene name keyword | ≤30 chars for search | `ListPtsSceneFail` if exceeded |
| PageSize | 10–1000 | `list-pts-scene` |

## Regions

```bash
aliyun pts get-all-regions --region cn-hangzhou
```

PTS is region-scoped; use the same region as the target system when possible.

## VPC / Intranet Testing

For private endpoints:

1. Configure VPC access in PTS console or via `get-user-vpcs` / `get-user-vpc-vswitch` / `get-user-vpc-security-group` CLI helpers
2. Delegate VPC creation to `alicloud-vpc-ops`
3. Ensure security group allows PTS agent egress to target port

## Billing

PTS charges by:

- VUM (virtual user minutes) or package plans (product edition dependent)
- Agent count × duration × load level

**Cost control:** Use `start-debug-pts-scene` before full runs; set `maxRunningTime`; use staged RPS ramp.

## SPOF & Safety

| Risk | Impact | Mitigation |
|------|--------|------------|
| Production URL in scene | Service outage | Safety gate + staging URL |
| Unbounded RPS | Target + PTS quota exhaustion | Cap `allRpsLimit`; ramp |
| Orphaned running scene | Continued cost | `stop-pts-scene` in recovery |
| Missing checkpoint | False success in reports | Add `checkPointList` |
