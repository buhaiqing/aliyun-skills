# Integration — PTS

> Version: 1.0.0 | Last Updated: 2026-06-16

## Go Bootstrap

### Prerequisites

- Go 1.21+ (1.24+ for JIT)
- `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `ALIBABA_CLOUD_REGION_ID`

### JIT Quick Start

```bash
cd "${SKILLS_DIR:-.}/.runtime/pts-jit"
cat > main.go << 'GOEOF'
// See api-sdk-usage.md minimal example
GOEOF
go mod init pts-jit
go get github.com/alibabacloud-go/pts-20201020/v2@v2.0.0
go run .
```

> Use repo `.runtime/` for ephemeral JIT workspaces per AGENTS.md §13.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | Access key |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | Secret (never log) |
| `ALIBABA_CLOUD_REGION_ID` | Yes | e.g. `cn-hangzhou` |

## CLI Plugin

```bash
aliyun plugin install --names aliyun-cli-pts
```

## Cross-Skill Delegation Matrix

| Scenario | Delegate To | When |
|----------|-------------|------|
| Create VPC for intranet PTS | `alicloud-vpc-ops` | `get-user-vpcs` empty |
| SLB backend unhealthy under load | `alicloud-slb-ops` | 5xx in PTS report |
| RDS slow under load | `alicloud-rds-ops` / `alicloud-das-ops` | DB latency spike |
| ECS scale-out after PTS | `alicloud-ess-ops` | Capacity planning |
| RAM policy for PTS | `alicloud-ram-ops` | `Forbidden` errors |
| CMS alarms on target | `alicloud-cms-ops` | Post-test monitoring |
| GCL before destructive ops | `alicloud-gcl-runner-ops` | `start-pts-scene`, `delete-pts-scene` |

## VPC Intranet Load Test Flow

```
1. alicloud-vpc-ops  → ensure VPC + vSwitch + SG
2. alicloud-pts-ops  → get-user-vpcs / bind in scene
3. alicloud-pts-ops  → start-debug-pts-scene
4. alicloud-pts-ops  → start-pts-scene (with safety gate)
5. alicloud-cms-ops  → target metrics correlation
```

## SkillOpt Wrapper

```bash
./scripts/pts-skillopt-wrapper.sh list-pts-scene --page-number 1 --page-size 10
```

See [skillopt-integration.md](skillopt-integration.md).

## OSS File Parameters

PTS scenes may reference OSS for CSV/data files (`FileParameterList`). For OSS upload issues → `alicloud-oss-ops`.
