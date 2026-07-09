---
name: alicloud-cen-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud Cloud Enterprise Network (CEN/CBN, 云企业网) — CEN instances, transit
  routers, VPC/VBR/VPN attachments, inter-region connections, bandwidth plans,
  route tables, route propagation/association, route maps, QoS, flow logs, and
  VBR health checks. Trigger on 云企业网, CEN, CBN, transit router, 转发路由器,
  跨地域互通, 专线互通, VPC跨地域, VBR接入, VPN接入, bandwidth package,
  route conflict, or connectivity through CEN. NOT for standalone VPC/EIP/NAT,
  ECS, RDS, SLB/ALB, billing, or RAM-only tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), optional CBN CLI
  plugin, Go 1.21+ runtime for JIT SDK fallback, valid API credentials, network
  access to Alibaba Cloud endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-09"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Cbn 2017-09-12 / https://help.aliyun.com/zh/cen/developer-reference/api-cbn-2017-09-12-overview"
  cli_applicability: cli-first
  cli_support_evidence: >-
    Confirmed via `aliyun help cbn`: Product `Cbn (Cloud Enterprise Network)`,
    Version `2017-09-12`, with CreateCen, DeleteCen, CreateTransitRouter,
    CreateTransitRouterVpcAttachment, CreateTransitRouterPeerAttachment,
    CreateTransitRouterRouteEntry, DescribeCens, DescribeTransitRouters, and
    related CEN APIs. CLI suggests optional `aliyun-cli-cbn` plugin.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

<!-- markdownlint-disable MD013 MD060 MD024 MD022 MD032 -->

# Alibaba Cloud Cloud Enterprise Network (CEN/CBN) Operations Skill

## Common JSON Paths (Centralized)

```text
# CreateCen:                         $.CenId
# DescribeCens:                      $.Cens.Cen[].CenId
# CreateCenBandwidthPackage:         $.CenBandwidthPackageId
# DescribeCenBandwidthPackages:      $.CenBandwidthPackages.CenBandwidthPackage[].CenBandwidthPackageId
# CreateTransitRouter:               $.TransitRouterId
# DescribeTransitRouters:            $.TransitRouters.TransitRouter[].TransitRouterId
# CreateTransitRouterVpcAttachment:  $.TransitRouterAttachmentId
# CreateTransitRouterVpcAttachment:  $.TransitRouterVpcAttachmentId (CLI/API variants may include either field)
# DescribeTransitRouterAttachments:  $.TransitRouterAttachments.TransitRouterAttachment[].TransitRouterAttachmentId
# CreateTransitRouterPeerAttachment: $.TransitRouterAttachmentId
# CreateTransitRouterRouteTable:     $.TransitRouterRouteTableId
# CreateTransitRouterRouteEntry:     $.TransitRouterRouteEntryId
# CreateFlowlog:                     $.FlowLogId
# Delete/Modify operations:          $.RequestId
```

## Overview

Alibaba Cloud Cloud Enterprise Network (CEN, API/CLI product code `cbn`) connects VPCs, VBRs, IPsec-VPN connections, and cross-region networks through Basic or Enterprise Edition transit routers. This skill is an **operational runbook** for agents: explicit scope, credential rules, pre-flight checks, **CLI-first execution** (`aliyun cbn`), JIT Go SDK fallback, response validation, safety gates, and failure recovery.

### CLI applicability

- **`cli_applicability: cli-first`**: `aliyun cbn` exposes CEN 2017-09-12 APIs. Use CLI as primary path; use JIT Go SDK only for CLI edge-case gaps or when CLI plugin behavior differs from OpenAPI.
- Install optional product plugin when available: `aliyun plugin install --names aliyun-cli-cbn`.

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/cbn-skillopt-wrapper.sh` for all CEN CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun cbn` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md) |
| Credentials | Read `{{env.*}}` only from environment; never ask user to paste or print secrets | [Integration](references/integration.md) |
| GCL | All write operations MUST pass GCL adversarial review before execution | [GCL Rubric](references/rubric.md) |

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|-----------------------------|
| 1 | Clear Boundaries | CEN/CBN-only triggers and explicit delegation to VPC/EIP/NAT/ECS/RDS/SLB skills |
| 2 | Structured I/O | `{{env.*}}`, `{{user.*}}`, `{{output.*}}` variables are documented and reused |
| 3 | Explicit Steps | Critical operations include Pre-flight → Execute → Validate → Recover |
| 4 | Failure Strategies | ≥10 CEN/networking errors with HALT/retry guidance in [troubleshooting](references/troubleshooting.md) |
| 5 | Single Responsibility | One product: Cloud Enterprise Network; dependent resources are verified/delegated, not managed here |

### Well-Architected Framework Integration

| Pillar | Skill Integration | Reference |
|--------|-------------------|-----------|
| Security | Least-privilege CBN RAM actions, credential masking, cross-account grant checks | [well-architected-assessment.md](references/well-architected-assessment.md) |
| Stability | Route conflict checks, redundant attachments, health checks, rollback-first changes | [well-architected-assessment.md](references/well-architected-assessment.md) |
| Cost | Bandwidth package sizing, inter-region billing, idle attachment detection | [well-architected-assessment.md](references/well-architected-assessment.md) |
| Efficiency | Batch describe patterns, idempotent ClientToken, dry-run when supported | [well-architected-assessment.md](references/well-architected-assessment.md) |
| Performance | Inter-region bandwidth, route convergence, flow logs, health-check latency | [monitoring.md](references/monitoring.md) |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Cloud Enterprise Network", "CEN", "CBN", "云企业网", "转发路由器", "Transit Router", "跨地域互通", "VPC跨地域", "VBR接入", "VPN接入".
- Task involves CEN instance lifecycle: create, describe, modify, delete.
- Task involves CEN bandwidth package lifecycle or association.
- Task involves transit router lifecycle, route tables, route entries, route propagation, route association, multicast domain, or QoS policy.
- Task involves attaching VPC/VBR/VPN/ECR to a transit router or detaching those attachments.
- Task involves cross-region peer attachments, route conflicts, health checks, flow logs, or connectivity troubleshooting through CEN.
- User asks to automate CEN operations via API, SDK, or `aliyun cbn` CLI.

### SHOULD NOT Use This Skill When

- Task is standalone VPC/vSwitch/EIP/NAT/VPN gateway provisioning outside CEN → delegate to `alicloud-vpc-ops`, `alicloud-eip-ops`, or `alicloud-nat-ops`.
- Task is ECS instance routing/security group only → delegate to `alicloud-ecs-ops`.
- Task is database endpoint or RDS/Redis connectivity only → delegate to the database skill after verifying CEN path if needed.
- Task is SLB/ALB listener/backend connectivity only → delegate to `alicloud-slb-ops` or `alicloud-alb-ops` after CEN path isolation.
- Task is billing/accounting only → delegate to `alicloud-billing-ops` when present.
- Task is RAM policy-only → delegate to `alicloud-ram-ops` when present.
- User insists on console-only instructions → state limitation; do not invent undocumented console steps.

## Delegation Rules

| Capability | Delegate To | Rule |
|------------|-------------|------|
| VPC/vSwitch creation or CIDR planning | `alicloud-vpc-ops` | CEN only attaches existing network instances; do not create VPCs here |
| EIP/NAT/VPN resource lifecycle | `alicloud-eip-ops`, `alicloud-nat-ops`, `alicloud-vpc-ops` | Verify dependency IDs; do not duplicate full flows |
| GCL quality gate | `alicloud-gcl-runner-ops` | Required before destructive or connectivity-impacting operations |
| CloudMonitor alarms | `alicloud-cms-ops` | Use this skill for CEN metric names and alarm intent; delegate alarm resource creation if needed |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime AK | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime SK | NEVER ask user; fail if unset; never print |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Default region | Use when operation needs a region; ask `{{user.region}}` if cross-region ambiguity exists |
| `{{user.region}}` | Region of child instance or transit router | Ask once; reuse |
| `{{user.cen_id}}` | CEN instance ID | Ask once or parse from `CreateCen` |
| `{{user.cen_name}}` | CEN instance name | Ask once for create/lookup |
| `{{user.transit_router_id}}` | Transit router ID | Ask once or parse from create/describe |
| `{{user.attachment_id}}` | Transit router attachment ID | Ask once or parse from create |
| `{{user.vpc_id}}` | Existing VPC ID | Ask once; verify via VPC skill/Describe where possible |
| `{{user.vswitch_id}}` | Existing vSwitch ID | Ask once; required for VPC attachment zone mappings |
| `{{user.zone_id}}` | Zone ID for VPC attachment | Ask once per mapping |
| `{{user.peer_region}}` | Peer region for inter-region attachment | Ask once; verify supported regions |
| `{{user.bandwidth_package_id}}` | CEN bandwidth package ID | Ask once or parse from create |
| `{{user.route_table_id}}` | Transit router route table ID | Ask once or parse from describe |
| `{{user.destination_cidr}}` | Route destination CIDR | Ask once; validate no conflict |
| `{{output.*}}` | API/CLI response fields | Parse using centralized JSON paths |

> **Credential masking is mandatory:** never log or echo `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, SDK configs, or full credential structs. Check existence only: `test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"`.

## API and Response Conventions

- OpenAPI and `aliyun help cbn <Operation>` are canonical for parameter names and response shapes.
- Use `--ClientToken` for idempotent create/modify operations whenever available.
- Use `--DryRun true` first when the operation supports `DryRun` and the operation changes routes or attachments.
- CEN is global at the instance level, but many child operations are regional. Always distinguish `{{user.region}}`, peer region, and child instance region.
- Deleting/detaching CEN resources can immediately disrupt connectivity. Run GCL and dependency checks first.

## Quick Start

### Verify setup

```bash
aliyun version
aliyun help cbn | head
# Optional enhanced plugin:
# aliyun plugin install --names aliyun-cli-cbn
# Credential existence check; do not print secret values:
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"
```

### First read-only command

```bash
aliyun cbn DescribeCens
```

### Common next steps

- [Core Concepts](references/core-concepts.md) — CEN, transit router, attachment, route propagation
- [CLI Usage](references/cli-usage.md) — verified `aliyun cbn` command map
- [Troubleshooting](references/troubleshooting.md) — route conflict and connectivity diagnostics

## Capabilities at a Glance

| Operation | Description | Risk |
|-----------|-------------|------|
| Create/Describe/Modify/Delete CEN | CEN instance lifecycle | Delete is High |
| Bandwidth package lifecycle | Create, associate, describe, delete CEN bandwidth package | Medium/High |
| Transit router lifecycle | Create/delete Enterprise Edition transit router | Delete is High |
| Attach VPC/VBR/VPN/ECR | Attach network instances to transit router | High — changes connectivity |
| Inter-region peer attachment | Build cross-region connectivity | High — cost and routing impact |
| Route table/entry/propagation | Manage transit routing | High — outage risk |
| Route map/QoS/flow log/health check | Traffic control, observability, resilience | Medium |
| Diagnose route conflict | Read-only route conflict and route table checks | Low |

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/cen-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun cen ...` 命令在执行时应替换为 `./scripts/cen-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun cen` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。

## Execution Flows (Agent-Readable)

### Operation: Create CEN Instance

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI support | `aliyun help cbn CreateCen` | Shows `CreateCen` parameters | Install/update CLI; retry |
| Credentials | env existence check only | AK/SK set | HALT — configure env |
| Duplicate name | `aliyun cbn DescribeCens --Name "{{user.cen_name}}"` | No existing intended CEN, or user chooses reuse | Reuse existing or choose new name |
| Idempotency token | Generate stable token from operation intent | Token available | HALT for automation; ask user for token if needed |

#### Execution — CLI (Primary)

```bash
CLIENT_TOKEN="cen-create-{{user.cen_name}}-{{user.request_id}}"
aliyun cbn CreateCen \
  --Name "{{user.cen_name}}" \
  --Description "{{user.description}}" \
  --ProtectionLevel REDUCED \
  --ClientToken "$CLIENT_TOKEN"
```

#### Validation

```bash
CEN_ID="{{output.cen_id}}"
aliyun cbn DescribeCens --CenId "$CEN_ID" \
  --output cols=CenId,Name,Status rows='Cens.Cen[]'
```

Success when `$.Cens.Cen[].CenId` contains `{{output.cen_id}}` and status is stable.

#### Recovery

| Error | Agent Action |
|-------|--------------|
| `InvalidParameter` | Fix name/description/protection level per help output; retry once if safe |
| `QuotaExceeded.Cen` | HALT — ask user to delete unused CEN or request quota increase |
| `Forbidden.RAM` | HALT — add CBN permissions |
| `Throttling` | Retry up to 3 times with exponential backoff |

### Operation: Create Transit Router

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CEN exists | `aliyun cbn DescribeCens --CenId "{{user.cen_id}}"` | One CEN returned | HALT — create/select CEN |
| TR service | `aliyun cbn CheckTransitRouterService` | Service activated | HALT — user activates service |
| Region support | `aliyun cbn DescribeChildInstanceRegions` | `{{user.region}}` supported | Ask for supported region |
| Duplicate TR | `aliyun cbn DescribeTransitRouters --CenId "{{user.cen_id}}" --RegionId "{{user.region}}"` | No matching intended TR, or reuse | Reuse/rename |

#### Execution — CLI

```bash
aliyun cbn CreateTransitRouter \
  --CenId "{{user.cen_id}}" \
  --RegionId "{{user.region}}" \
  --TransitRouterName "{{user.transit_router_name}}" \
  --ClientToken "tr-create-{{user.cen_id}}-{{user.region}}-{{user.request_id}}"
```

#### Validation

```bash
aliyun cbn DescribeTransitRouters \
  --CenId "{{user.cen_id}}" \
  --RegionId "{{user.region}}" \
  --TransitRouterId "{{output.transit_router_id}}"
```

Poll every 5s up to 300s until TR is present and not in a deleting/failed state.

### Operation: Attach VPC to Transit Router

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| GCL required | Run `alicloud-gcl-runner-ops` with this operation | PASS | ABORT on Safety=0 |
| Transit router exists | `DescribeTransitRouters` | TR present in region | HALT |
| VPC/vSwitch exists | Delegate/verify with VPC describe; require VPC ID and zone mappings | IDs valid | HALT |
| CIDR overlap | `DescribeRouteConflict` and VPC CIDR inventory | No blocking conflict | HALT or redesign CIDR/routes |
| Existing attachment | `DescribeTransitRouterAttachments` filtered by VPC | No duplicate, or reuse | Reuse existing attachment |
| Dry run | `CreateTransitRouterVpcAttachment --DryRun true ...` | Returns `DryRunOperation` | Fix parameters before execution |

#### Execution — CLI

```bash
aliyun cbn CreateTransitRouterVpcAttachment \
  --RegionId "{{user.region}}" \
  --CenId "{{user.cen_id}}" \
  --TransitRouterId "{{user.transit_router_id}}" \
  --VpcId "{{user.vpc_id}}" \
  --ZoneMappings.1.ZoneId "{{user.zone_id_1}}" \
  --ZoneMappings.1.VSwitchId "{{user.vswitch_id_1}}" \
  --AutoPublishRouteEnabled true \
  --TransitRouterAttachmentName "{{user.attachment_name}}" \
  --ClientToken "tr-vpc-attach-{{user.vpc_id}}-{{user.request_id}}"
```

For multi-AZ, add additional `--ZoneMappings.n.ZoneId` / `--ZoneMappings.n.VSwitchId` pairs.

#### Validation

```bash
aliyun cbn DescribeTransitRouterAttachments \
  --RegionId "{{user.region}}" \
  --TransitRouterId "{{user.transit_router_id}}" \
  --TransitRouterAttachmentId "{{output.attachment_id}}"
```

Success when attachment enters `Attached`/stable state and routes propagate as intended.

#### Recovery

| Error | Agent Action |
|-------|--------------|
| `RouteConflict` / `InvalidCidrBlock.Overlapped` | HALT — show conflicting CIDR/routes; require network redesign |
| `IncorrectStatus.TransitRouter` | Wait then retry if transitioning; HALT if failed/deleting |
| `ResourceAlreadyAssociated` | Treat as idempotent; describe and reuse existing attachment |
| `DryRunOperation` | Expected for dry-run success; proceed only after user confirms |

### Operation: Create Inter-Region Peer Attachment

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Cost confirmation | User confirms bandwidth/cross-region billing | Explicit confirmation | HALT |
| Both TRs exist | `DescribeTransitRouters` in local and peer regions | Both present | HALT |
| Bandwidth plan/limit | `DescribeCenInterRegionBandwidthLimits` or bandwidth package describe | Sufficient bandwidth | HALT or resize |
| Route conflict | `DescribeRouteConflict` for affected networks | No blocking conflict | HALT |

#### Execution — CLI

```bash
aliyun cbn CreateTransitRouterPeerAttachment \
  --RegionId "{{user.region}}" \
  --CenId "{{user.cen_id}}" \
  --TransitRouterId "{{user.transit_router_id}}" \
  --PeerTransitRouterRegionId "{{user.peer_region}}" \
  --PeerTransitRouterId "{{user.peer_transit_router_id}}" \
  --Bandwidth "{{user.bandwidth_mbps}}" \
  --TransitRouterAttachmentName "{{user.peer_attachment_name}}" \
  --ClientToken "tr-peer-{{user.region}}-{{user.peer_region}}-{{user.request_id}}"
```

#### Validation

Describe attachment on both sides, then verify route table association/propagation and expected routes.

### Operation: Create Transit Router Route Entry

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| GCL required | Run quality gate | PASS | ABORT on Safety=0 |
| Route table exists | `DescribeTransitRouterRouteTables` | route table found | HALT |
| Destination CIDR safe | Compare existing route entries and child CIDRs | No overlap/unintended blackhole | HALT |
| Next hop attachment exists | `DescribeTransitRouterAttachments` | stable attachment | HALT |
| Rollback captured | Current route table exported | JSON saved in trace | HALT for production changes |

#### Execution — CLI

```bash
aliyun cbn CreateTransitRouterRouteEntry \
  --TransitRouterRouteTableId "{{user.route_table_id}}" \
  --TransitRouterRouteEntryDestinationCidrBlock "{{user.destination_cidr}}" \
  --TransitRouterRouteEntryNextHopType Attachment \
  --TransitRouterRouteEntryNextHopId "{{user.attachment_id}}" \
  --TransitRouterRouteEntryName "{{user.route_entry_name}}" \
  --ClientToken "tr-route-{{user.route_table_id}}-{{user.destination_cidr}}-{{user.request_id}}"
```

#### Validation

```bash
aliyun cbn ListTransitRouterRouteEntries \
  --TransitRouterRouteTableId "{{user.route_table_id}}" \
  --TransitRouterRouteEntryDestinationCidrBlock "{{user.destination_cidr}}"
```

Success when the route exists and next hop equals `{{user.attachment_id}}`.

### Operation: Delete or Detach CEN Resource

#### Pre-flight Safety Gate

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Explicit confirmation | User must state exact resource ID and impact acknowledgement | Confirmed | HALT |
| GCL required | Run GCL with operation and resource ID | PASS | ABORT |
| Dependency cascade | For CEN/TR/attachment: describe child attachments, route entries, associations, propagations, bandwidth package associations | No dependents or approved ordered cleanup | HALT |
| Rollback plan | Export current topology/routes to `.runtime/audit/cen-ops/` or trace | Available | HALT for production |
| Credential hygiene | Secret not present in command/log | Clean | ABORT if leaked |

#### Execution — CLI Examples

```bash
# Delete route entry after validation
aliyun cbn DeleteTransitRouterRouteEntry \
  --TransitRouterRouteTableId "{{user.route_table_id}}" \
  --TransitRouterRouteEntryId "{{user.route_entry_id}}"

# Delete VPC attachment only after route/propagation cleanup
aliyun cbn DeleteTransitRouterVpcAttachment \
  --RegionId "{{user.region}}" \
  --TransitRouterAttachmentId "{{user.attachment_id}}"

# Delete CEN only when no network instances, TRs, bandwidth packages, or routes remain
aliyun cbn DeleteCen --CenId "{{user.cen_id}}"
```

#### Validation

Poll corresponding `Describe*` until resource is absent or terminal deleted state, max 300s. Treat `NotFound` after delete as success only if the pre-flight resource ID matches exactly.

## Failure Recovery Summary

| Error Pattern | Max Retries | Agent Action |
|---------------|-------------|--------------|
| `InvalidParameter` | 0-1 | Fix against `aliyun help cbn <Operation>`; retry once if safe |
| `Forbidden.RAM` / `NoPermission` | 0 | HALT — request CBN RAM permissions |
| `QuotaExceeded` | 0 | HALT — request quota or cleanup unused resources |
| `InsufficientBalance` | 0 | HALT — billing action required |
| `Throttling` / 429 | 3 | Exponential backoff; preserve RequestId |
| `InternalError` / 5xx | 3 | Retry, then HALT with RequestId |
| `RouteConflict` | 0 | HALT — run route conflict diagnostics |
| `IncorrectStatus` | 3 if transitioning | Poll stable state; HALT if failed/deleting |
| `DependencyViolation` | 0 | HALT — list dependents and ordered cleanup |
| `DryRunOperation` | n/a | Dry-run success; ask confirmation before real write |

See [Troubleshooting](references/troubleshooting.md) for full taxonomy.

## Prerequisites

1. Install/verify CLI:

   ```bash
   aliyun version
   aliyun help cbn
   # Optional plugin:
   aliyun plugin install --names aliyun-cli-cbn
   ```

2. Configure credentials using environment variables; never print secrets.
3. For SDK fallback, see [Integration](references/integration.md).

## Quality Gate (GCL)

| Required? | max_iter | Most-scrutinized Ops | References |
|-----------|----------|----------------------|------------|
| required | 2 | DeleteCen, DeleteTransitRouter*, DeleteTransitRouter*Attachment, Create/Delete route entries, route propagation/association, peer attachment, bandwidth changes | [rubric.md](references/rubric.md), [prompt-templates.md](references/prompt-templates.md) |

Changelog: GCL 1.0.0 added at skill creation for CEN/CBN high-impact networking operations.

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting Guide](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)
- [Idempotency Checklist](references/idempotency-checklist.md)
- [GCL Rubric](references/rubric.md)
- [GCL Prompt Templates](references/prompt-templates.md)

## Operational Best Practices

- Prefer read-only topology export before any write.
- Use `DryRun` where supported and record `RequestId` for every write.
- Make route changes during a maintenance window; prepare rollback route entries.
- Keep CEN route changes separate from VPC resource creation; delegate dependent resources.
- Avoid broad route propagation without route conflict checks.

## Token Efficiency Guidelines (P0)

- Use `Describe*` APIs for current quotas/regions/topology instead of static tables.
- Keep detailed operation maps in references; SKILL.md contains only critical execution flows.
- Centralize JSON paths in this file and `api-sdk-usage.md`.
- Use YAML anchors in `assets/example-config.yaml`.
- Put advanced diagnosis details in references, not in SKILL.md.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-09 | Initial CEN/CBN operations skill with CLI-first flows, GCL, references, and eval assets |
