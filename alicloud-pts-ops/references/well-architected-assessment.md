# Well-Architected Assessment — PTS

> Version: 1.0.0 | Last Updated: 2026-06-16

## 1. Security (安全)

### 1.1 IAM

| Operation | RAM Action | Scope |
|-----------|------------|-------|
| List/Get scene | `pts:ListPtsScene`, `pts:GetPtsScene` | `acs:pts:*:*:scene/*` |
| Create/Save | `pts:CreatePtsScene`, `pts:SavePtsScene` | scene scope |
| Start/Stop test | `pts:StartPtsScene`, `pts:StopPtsScene` | scene scope |
| Delete | `pts:DeletePtsScene` | specific scene |
| Reports | `pts:ListPtsReports`, `pts:GetPtsReportDetails` | read |

Use least-privilege; separate RAM user for CI load tests.

### 1.2 Credential & Data

- Never embed AK in Scene JSON or JMeter scripts
- Use PTS global parameters for secrets (rotated outside git)
- Mask credentials in logs per AGENTS.md §8

### 1.3 Network

- Prefer VPC-isolated targets for intranet APIs
- Restrict PTS to staging URLs via naming convention (`staging-*`)

## 2. Stability (稳定)

| Practice | Rationale |
|----------|-----------|
| Always `start-debug-pts-scene` before full run | Catches config errors cheaply |
| RPS ramp (`allRpsBegin` → `allRpsLimit`) | Avoids thundering herd |
| `maxRunningTime` cap | Prevents runaway cost/outage |
| `stop-pts-scene` in runbook | Emergency brake |
| Baseline per release | Regression detection |

## 3. Cost (成本)

| Pattern | Detection | Action |
|---------|-----------|--------|
| Long running scene | Status `Running` > planned | Auto-stop via cron + `stop-pts-scene` |
| Over-provisioned agents | Low target utilization | Reduce `agentCount` |
| Repeated full tests | Many reports same day | Use debug + smaller RPS first |

PTS billing: VUM / package — monitor usage in billing console.

## 4. Efficiency (效率)

- Store Scene JSON in git (without secrets) for CI/CD
- `list-pts-scene --key-word` for discovery
- Batch delete stale scenes: `delete-pts-scenes`
- JMeter env reuse via `save-env` / `list-envs`

## 5. Performance (性能)

| Goal | PTS Knob | Target Side |
|------|----------|-------------|
| Peak TPS | `allRpsLimit`, `agentCount` | SLB/ECS scale |
| Latency SLA | Checkpoints on RT | App tuning |
| Soak test | High `maxRunningTime`, moderate RPS | Memory leak detection |

Correlate PTS report with CMS metrics on target (see [monitoring.md](monitoring.md)).
