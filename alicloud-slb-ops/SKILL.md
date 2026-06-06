---
name: alicloud-slb-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud SLB (Classic Load Balancer / CLB) — load balancer instances, listeners,
  virtual server groups, backend servers, certificates, access control lists,
  and forwarding rules. User mentions SLB, CLB, 负载均衡, 传统型负载均衡,
  Classic Load Balancer, or describes load balancing issues (dropped connections,
  unhealthy backends, certificate errors) even without naming the product
  directly. Not for ALB (Application Load Balancer) or NLB (Network Load
  Balancer) — those have separate skills when present.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.1.0"
  last_updated: "2026-06-04"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "SLB 2014-05-15 / https://www.alibabacloud.com/help/en/slb"
  cli_applicability: cli-first
  cli_support_evidence: >-
    Confirmed via `aliyun help slb` — SLB is fully supported by the official
    aliyun CLI. All core operations (CRUD for instances, listeners, vserver
    groups, backend servers, certificates, ACLs, rules) have matching CLI commands.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud SLB Operations Skill

## Common JSON Paths (Centralized)

```
# Create LB:           $.{LoadBalancerId,Address,VSwitchId,VpcId}
# Describe LBs:        $.LoadBalancers.LoadBalancer[].{LoadBalancerId,LoadBalancerStatus,Address}
# Describe LB Attr:    $.{LoadBalancerId,LoadBalancerStatus,Address,VpcId,CreateTime}
# Create VServerGroup: $.VServerGroupId
# Describe VSGs:       $.VServerGroups.VServerGroup[].VServerGroupId
# Upload Cert:         $.ServerCertificateId
# Create ACL:          $.AclId
# Create Rules:        $.Rules.Rule[].RuleId
# Delete/Set/Modify:   $.RequestId
```

## Overview

Alibaba Cloud SLB (Server Load Balancer, also known as CLB — Classic Load Balancer)
provides traffic distribution across multiple backend servers to improve service
availability and elasticity. This skill is an **operational runbook** for agents:
explicit scope, credential rules, pre-flight checks, **cli-first execution**
(official **`aliyun` CLI** as primary path, **JIT Go SDK** as fallback), response
validation, and failure recovery.

### CLI applicability (repository policy)

- **`cli_applicability: cli-first`:** Official `aliyun` fully supports SLB. CLI is
the **primary** execution path for all operations. JIT Go SDK is the **fallback**
only when CLI lacks support for a specific edge-case operation.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "Alibaba Cloud SLB" OR "CLB" OR "负载均衡" OR "传统型负载均衡"
  OR "Classic Load Balancer"
- Task involves CRUD or lifecycle operations on **SLB instances** (create, describe,
  modify, delete, list, start, stop)
- Task involves **listeners** (create, describe, modify, delete TCP/UDP/HTTP/HTTPS
  listeners)
- Task involves **virtual server groups** (create, describe, modify, delete,
  add/remove backend servers)
- Task involves **backend servers** (add, remove, set weights, describe)
- Task involves **certificates** (upload, describe, delete server/CA certificates)
- Task involves **access control lists (ACL)** (create, describe, modify, delete,
  add/remove entries)
- Task involves **forwarding rules** (create, describe, modify, delete)
- Task involves **health check configuration** or **session persistence**
- Task keywords: 负载均衡, SLB, CLB, listener, 监听, vserver group, 虚拟服务器组,
  backend server, 后端服务器, certificate, 证书, ACL, 访问控制, forwarding rule,
  转发规则, health check, 健康检查
- User asks to deploy, configure, troubleshoot, or monitor SLB **via API, SDK,
  CLI, or automation**

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to:
  `alicloud-billing-ops` (when present)
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops` (when present)
- Task is about **ALB (Application Load Balancer)** → ALB uses a different API
  surface; note limitation and suggest ALB-specific skill if available
- Task is about **NLB (Network Load Balancer)** → NLB uses a different API surface;
  note limitation and suggest NLB-specific skill if available
- Task is about **ECS / compute only** → delegate to: `alicloud-ecs-ops`
- Task is about **VPC / networking only** → delegate to: `alicloud-vpc-ops` (when present)
- User insists on **console-only** flows with no API → state limitation; do not
  invent undocumented HTTP steps

### Delegation Rules

- If creating an SLB instance in a VPC, verify VPC and VSwitch exist (via
  `alicloud-vpc-ops`) before SLB creation.
- If adding backend servers, verify ECS instances exist (via `alicloud-ecs-ops`)
  and are in the same region/VPC.
- If uploading certificates, ensure certificate content and private key are valid
  PEM format.
- Multi-product requests: handle each product with its skill; do not merge
  unrelated APIs into one ambiguous flow.

#### ECS Delegation Rules (后端异常联动)

| Scenario | Condition | Delegate To | Action |
|----------|-----------|-------------|--------|
| 后端异常 | Backend server health check failure | `alicloud-ecs-ops` | ECS 实例诊断 |
| 健康检查失败 | Health check status abnormal | `alicloud-ecs-ops` | ECS 实例网络/端口检查 |

#### Multi-Index Anomaly Patterns (多指标异常模式)

| Pattern ID | Description | Detection Logic | Recommended Action |
|------------|-------------|-----------------|---------------------|
| 1 | 连接数-响应延迟瓶颈 | ActiveConnection 持续 > 80% 且 LatencyP50 > 500ms | 检查后端服务器性能 |
| 2 | 健康检查失败率突增 | HealthCheck failed ratio > 50% in 5min | 检查后端服务可用性 |
| 3 | 后端服务器不均衡 | Server weight imbalance > 3x | 调整后端权重 |
| 4 | 流量突增异常 | QPS 突增 > 200% baseline | 排查异常流量/攻击 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.region}}` | User-supplied region | Ask once; reuse |
| `{{user.load_balancer_id}}` | User-supplied SLB instance ID | Ask once; reuse |
| `{{user.load_balancer_name}}` | User-supplied SLB instance name | Ask once; reuse |
| `{{user.listener_port}}` | User-supplied listener port | Ask once; reuse |
| `{{user.listener_protocol}}` | User-supplied protocol (tcp/udp/http/https) | Ask once; reuse |
| `{{user.vserver_group_id}}` | User-supplied vserver group ID | Ask once; reuse |
| `{{user.vserver_group_name}}` | User-supplied vserver group name | Ask once; reuse |
| `{{user.backend_server_id}}` | User-supplied ECS/ENI/ECI instance ID | Ask once; reuse |
| `{{user.certificate_id}}` | User-supplied certificate ID | Ask once; reuse |
| `{{user.acl_id}}` | User-supplied ACL ID | Ask once; reuse |
| `{{user.rule_id}}` | User-supplied forwarding rule ID | Ask once; reuse |
| `{{output.load_balancer_id}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.listener_port}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.vserver_group_id}}` | From last API or CLI JSON response | Parse per OpenAPI or verified CLI path |
| `{{output.request_id}}` | From API response | For support / correlation |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response shapes.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** Document client request tokens, duplicate names, and
  `LoadBalancerAlreadyExists` behavior per API.
- **ClientToken:** For write operations (CreateLoadBalancer, CreateVServerGroup, etc.),
  generate a unique `ClientToken` (UUID v4) per logical request. If the same
  operation is retried due to network timeout, reuse the same `ClientToken` to
  ensure idempotency. The API returns the same result for duplicate requests with
  the same `ClientToken` within 24 hours.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| CreateLoadBalancer | `$.LoadBalancerId` | string | New SLB instance ID |
| CreateLoadBalancer | `$.Address` | string | Assigned IP address |
| CreateLoadBalancer | `$.VSwitchId` | string | VSwitch ID |
| CreateLoadBalancer | `$.VpcId` | string | VPC ID |
| DescribeLoadBalancers | `$.LoadBalancers.LoadBalancer[].LoadBalancerId` | array | Instance IDs |
| DescribeLoadBalancers | `$.LoadBalancers.LoadBalancer[].LoadBalancerStatus` | string | Instance status |
| DescribeLoadBalancers | `$.LoadBalancers.LoadBalancer[].Address` | string | IP address |
| DescribeLoadBalancers | `$.LoadBalancers.LoadBalancer[].AddressType` | string | internet / intranet |
| DescribeLoadBalancers | `$.LoadBalancers.LoadBalancer[].RegionId` | string | Region ID |
| DescribeLoadBalancerAttribute | `$.LoadBalancerId` | string | Instance ID |
| DescribeLoadBalancerAttribute | `$.LoadBalancerStatus` | string | Status |
| DescribeLoadBalancerAttribute | `$.Address` | string | IP address |
| DescribeLoadBalancerAttribute | `$.Bandwidth` | int | Bandwidth (Mbps) |
| DescribeLoadBalancerAttribute | `$.VpcId` | string | VPC ID |
| DescribeLoadBalancerAttribute | `$.VSwitchId` | string | VSwitch ID |
| DescribeLoadBalancerAttribute | `$.CreateTime` | string | ISO 8601 timestamp |
| DescribeLoadBalancerAttribute | `$.ListenerPorts.ListenerPort[]` | array | Listener ports |
| DescribeLoadBalancerAttribute | `$.ListenerPortsAndProtocol.ListenerPortAndProtocol[].ListenerPort` | array | Listener ports with protocol |
| DescribeLoadBalancerAttribute | `$.DeleteProtection` | string | on / off |
| DescribeLoadBalancerAttribute | `$.ModificationProtectionStatus` | string | ConsoleProtection / NonProtection |
| SetLoadBalancerStatus | `$.RequestId` | string | Request ID |
| DeleteLoadBalancer | `$.RequestId` | string | Request ID |
| CreateVServerGroup | `$.VServerGroupId` | string | New vserver group ID |
| DescribeVServerGroups | `$.VServerGroups.VServerGroup[].VServerGroupId` | array | Group IDs |
| DescribeVServerGroupAttribute | `$.VServerGroupId` | string | Group ID |
| DescribeVServerGroupAttribute | `$.BackendServers.BackendServer[].ServerId` | array | Backend server IDs |
| DeleteVServerGroup | `$.RequestId` | string | Request ID |
| DescribeLoadBalancerListeners | `$.Listeners.Listener[].ListenerPort` | array | Listener ports |
| DescribeLoadBalancerListeners | `$.Listeners.Listener[].Protocol` | string | Protocol |
| DescribeLoadBalancerListeners | `$.Listeners.Listener[].ListenerForward` | string | Forwarding config |
| UploadServerCertificate | `$.ServerCertificateId` | string | New certificate ID |
| DescribeServerCertificates | `$.ServerCertificates.ServerCertificate[].ServerCertificateId` | array | Certificate IDs |
| DeleteServerCertificate | `$.RequestId` | string | Request ID |
| CreateAccessControlList | `$.AclId` | string | New ACL ID |
| DescribeAccessControlLists | `$.Acls.Acl[].AclId` | array | ACL IDs |
| DeleteAccessControlList | `$.RequestId` | string | Request ID |
| CreateRules | `$.Rules.Rule[].RuleId` | array | New rule IDs |
| DescribeRules | `$.Rules.Rule[].RuleId` | array | Rule IDs |
| DeleteRules | `$.RequestId` | string | Request ID |

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateLoadBalancer | — | `active` | 5s | 120s |
| SetLoadBalancerStatus (stop) | `active` | `inactive` | 5s | 60s |
| SetLoadBalancerStatus (start) | `inactive` | `active` | 5s | 60s |
| DeleteLoadBalancer | any stable state | absent | 5s | 120s |
| CreateVServerGroup | — | `Available` | 5s | 60s |
| DeleteVServerGroup | `Available` | absent | 5s | 60s |
| CreateLoadBalancerTCPListener | — | `running` | 5s | 60s |
| CreateLoadBalancerUDPListener | — | `running` | 5s | 60s |
| CreateLoadBalancerHTTPListener | — | `running` | 5s | 60s |
| CreateLoadBalancerHTTPSListener | — | `running` | 5s | 60s |



## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI primary, SDK fallback) → Validate → Recover**.

---

### Operation: Create Load Balancer

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| SDK / deps | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures env |
| Region | `aliyun slb DescribeRegions` | `{{user.region}}` supported | Suggest valid region |
| VPC/VSwitch | `aliyun vpc DescribeVpcs` / `DescribeVSwitches` | VPC and VSwitch exist | Delegate to `alicloud-vpc-ops` |
| Quota | `aliyun slb DescribeAvailableResource` | Sufficient quota | HALT; user raises quota |

#### Execution — CLI (Primary Path)

```bash
aliyun slb CreateLoadBalancer \
  --RegionId "{{user.region}}" \
  --LoadBalancerName "{{user.load_balancer_name}}" \
  --AddressType "{{user.address_type|internet}}" \
  --InternetChargeType "{{user.internet_charge_type|paybytraffic}}" \
  --VpcId "{{user.vpc_id}}" \
  --VSwitchId "{{user.vswitch_id}}" \
  --Bandwidth "{{user.bandwidth|10}}" \
  --LoadBalancerSpec "{{user.load_balancer_spec|slb.s1.small}}" \
  --ClientToken "{{output.client_token}}"
```

> **Idempotency:** Include `--ClientToken` (UUID v4) for idempotency. Reuse the
> same token when retrying the same logical request within 24 hours.

> **Note:** Output is JSON by default. Parse `LoadBalancerId` from response.

> **Important:** CLB subscription instances stopped new purchases on 2024-12-01.
  Only pay-as-you-go instances can be created.

#### Execution — JIT Go SDK (Fallback Path)

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Read `{{output.load_balancer_id}}` from `$.LoadBalancerId`.
2. Poll **DescribeLoadBalancerAttribute** until `LoadBalancerStatus` is `active`:

```bash
for i in $(seq 1 24); do
  STATUS=$(aliyun slb DescribeLoadBalancerAttribute \
    --LoadBalancerId "{{output.load_balancer_id}}" \
    --output cols=LoadBalancerStatus rows=LoadBalancerStatus)
  [ "$STATUS" = "active" ] && break
  sleep 5
done
```

3. On success, report `{{output.load_balancer_id}}`, `Address`, and key fields.
4. On terminal failure, go to **Failure Recovery**.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / 400 | 0–1 | — | Fix args from OpenAPI; retry once if safe |
| `QuotaExceeded` / `LoadBalancerQuotaExceeded` | 0 | — | HALT |
| `InsufficientBalance` | 0 | — | HALT |
| `LoadBalancerAlreadyExists` | 0 | — | Ask reuse vs new name |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Describe Load Balancers

#### Execution — CLI

```bash
# Describe all SLB instances in region
aliyun slb DescribeLoadBalancers --RegionId "{{user.region}}"

# Describe specific instance
aliyun slb DescribeLoadBalancers \
  --RegionId "{{user.region}}" \
  --LoadBalancerId "{{user.load_balancer_id}}"

# Extract specific fields with JMESPath
aliyun slb DescribeLoadBalancers --RegionId "{{user.region}}" \
  --output cols=LoadBalancerId,LoadBalancerStatus,Address,AddressType rows=LoadBalancers.LoadBalancer[].{LoadBalancerId,LoadBalancerStatus,Address,AddressType}
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Load Balancer ID | `$.LoadBalancers.LoadBalancer[].LoadBalancerId` | e.g., lb-bp67acfmxazb4ph*** |
| Name | `$.LoadBalancers.LoadBalancer[].LoadBalancerName` | Plain text |
| Status | `$.LoadBalancers.LoadBalancer[].LoadBalancerStatus` | active, inactive |
| Address | `$.LoadBalancers.LoadBalancer[].Address` | IP address |
| Address Type | `$.LoadBalancers.LoadBalancer[].AddressType` | internet / intranet |
| Region | `$.LoadBalancers.LoadBalancer[].RegionId` | Plain text |
| VPC ID | `$.LoadBalancers.LoadBalancer[].VpcId` | Plain text |
| VSwitch ID | `$.LoadBalancers.LoadBalancer[].VSwitchId` | Plain text |
| Bandwidth | `$.LoadBalancers.LoadBalancer[].Bandwidth` | Mbps |
| Spec | `$.LoadBalancers.LoadBalancer[].LoadBalancerSpec` | e.g., slb.s1.small |
| Create Time | `$.LoadBalancers.LoadBalancer[].CreateTime` | ISO 8601 |
| Pay Type | `$.LoadBalancers.LoadBalancer[].PayType` | PayOnDemand / PrePay |

---

### Operation: Describe Load Balancer Attribute

#### Execution — CLI

```bash
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId "{{user.load_balancer_id}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Load Balancer ID | `$.LoadBalancerId` | Plain text |
| Status | `$.LoadBalancerStatus` | active / inactive |
| Address | `$.Address` | IP address |
| Network Type | `$.NetworkType` | vpc / classic |
| Address Type | `$.AddressType` | internet / intranet |
| VPC ID | `$.VpcId` | Plain text |
| VSwitch ID | `$.VSwitchId` | Plain text |
| Bandwidth | `$.Bandwidth` | Mbps |
| Spec | `$.LoadBalancerSpec` | e.g., slb.s1.small |
| Listener Ports | `$.ListenerPorts.ListenerPort[]` | Array of ports |
| Listener Ports (HTTPS) | `$.ListenerPortsAndProtocol.ListenerPortAndProtocol[].ListenerPort` | With protocol info |
| Delete Protection | `$.DeleteProtection` | on / off |
| Modification Protection | `$.ModificationProtectionStatus` | ConsoleProtection / NonProtection |

---

### Operation: Set Load Balancer Status

#### Pre-flight

- Verify instance exists.
- **MUST** obtain explicit confirmation for status changes that may impact traffic.

#### Execution — CLI

```bash
# Stop the SLB instance (inactive)
aliyun slb SetLoadBalancerStatus \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --LoadBalancerStatus "inactive"

# Start the SLB instance (active)
aliyun slb SetLoadBalancerStatus \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --LoadBalancerStatus "active"
```

#### Post-execution Validation

Poll until `LoadBalancerStatus` matches target:

```bash
for i in $(seq 1 12); do
  STATUS=$(aliyun slb DescribeLoadBalancerAttribute \
    --LoadBalancerId "{{user.load_balancer_id}}" \
    --output cols=LoadBalancerStatus rows=LoadBalancerStatus)
  [ "$STATUS" = "{{user.target_status}}" ] && break
  sleep 5
done
```

---

### Operation: Set Load Balancer Name

#### Pre-flight

- Verify instance exists.

#### Execution — CLI

```bash
aliyun slb SetLoadBalancerName \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --LoadBalancerName "{{user.new_load_balancer_name}}"
```

#### Post-execution Validation

Verify name change via DescribeLoadBalancerAttribute.

---

### Operation: Modify Load Balancer Instance Spec

#### Pre-flight

- Verify instance exists and is `active`.
- **MUST** warn user that changing spec may cause brief connection interruption.

#### Execution — CLI

```bash
aliyun slb ModifyLoadBalancerInstanceSpec \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --LoadBalancerSpec "{{user.new_load_balancer_spec}}"
```

> **Note:** Available specs: slb.s1.small, slb.s2.small, slb.s2.medium, slb.s3.small,
  slb.s3.medium, slb.s3.large. Performance guarantee instances only.

#### Post-execution Validation

Poll until spec change is reflected:

```bash
for i in $(seq 1 12); do
  SPEC=$(aliyun slb DescribeLoadBalancerAttribute \
    --LoadBalancerId "{{user.load_balancer_id}}" \
    --output cols=LoadBalancerSpec rows=LoadBalancerSpec)
  [ "$SPEC" = "{{user.new_load_balancer_spec}}" ] && break
  sleep 5
done
```

---

### Operation: Delete Load Balancer

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: irreversible delete of
  `{{user.load_balancer_name}}` (`{{user.load_balancer_id}}`).
- **MUST NOT** proceed without clear user assent.
- Verify instance has **no deletion protection** enabled (`DeleteProtection` is `off`).
  If `on`, user must disable it first via `SetLoadBalancerDeleteProtection`.
- **Recommendation:** Verify no active listeners or backend dependencies; warn user
  if dependencies exist.

#### Execution — CLI

```bash
aliyun slb DeleteLoadBalancer \
  --RegionId "{{user.region}}" \
  --LoadBalancerId "{{user.load_balancer_id}}"
```

> **Note:** `--RegionId` is required for the delete operation to correctly route
> the request.

#### Post-execution Validation

Poll **DescribeLoadBalancers** until instance is absent (returns empty list or
`LoadBalancerNotFound`) within **120s**:

```bash
for i in $(seq 1 24); do
  RESULT=$(aliyun slb DescribeLoadBalancers \
    --RegionId "{{user.region}}" \
    --LoadBalancerId "{{user.load_balancer_id}}" \
    --output cols=TotalCount rows=TotalCount)
  [ "$RESULT" = "0" ] && break
  sleep 5
done
```

---

### Operation: Create TCP Listener

#### Pre-flight

- Verify SLB instance exists and is `active`.
- Verify `{{user.listener_port}}` is not already in use on this SLB.

#### Execution — CLI

```bash
aliyun slb CreateLoadBalancerTCPListener \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --BackendServerPort "{{user.backend_server_port}}" \
  --Bandwidth "{{user.bandwidth|-1}}" \
  --Scheduler "{{user.scheduler|wrr}}" \
  --HealthCheckType "{{user.health_check_type|tcp}}" \
  --PersistenceTimeout "{{user.persistence_timeout|0}}" \
  --EstablishedTimeout "{{user.established_timeout|500}}"
```

> **Note:** `Bandwidth` = -1 means unlimited.

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

Verify listener appears in DescribeLoadBalancerListeners:

```bash
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerProtocol tcp
```

---

### Operation: Create HTTP Listener

#### Pre-flight

- Verify SLB instance exists and is `active`.

#### Execution — CLI

```bash
aliyun slb CreateLoadBalancerHTTPListener \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --BackendServerPort "{{user.backend_server_port}}" \
  --Bandwidth "{{user.bandwidth|-1}}" \
  --Scheduler "{{user.scheduler|wrr}}" \
  --StickySession "{{user.sticky_session|off}}" \
  --HealthCheck "{{user.health_check|on}}" \
  --XForwardedFor "{{user.x_forwarded_for|on}}"
```

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

---

### Operation: Create HTTPS Listener

#### Pre-flight

- Verify SLB instance exists and is `active`.
- Verify server certificate exists (or upload one first).

#### Execution — CLI

```bash
aliyun slb CreateLoadBalancerHTTPSListener \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --BackendServerPort "{{user.backend_server_port}}" \
  --Bandwidth "{{user.bandwidth|-1}}" \
  --Scheduler "{{user.scheduler|wrr}}" \
  --ServerCertificateId "{{user.certificate_id}}" \
  --StickySession "{{user.sticky_session|off}}" \
  --HealthCheck "{{user.health_check|on}}" \
  --XForwardedFor "{{user.x_forwarded_for|on}}"
```

> **Note:** `ServerCertificateId` is required for HTTPS listeners.

---

### Operation: Create UDP Listener

#### Pre-flight

- Verify SLB instance exists and is `active`.
- Verify `{{user.listener_port}}` is not already in use on this SLB.

#### Execution — CLI

```bash
aliyun slb CreateLoadBalancerUDPListener \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --BackendServerPort "{{user.backend_server_port}}" \
  --Bandwidth "{{user.bandwidth|-1}}" \
  --Scheduler "{{user.scheduler|wrr}}" \
  --PersistenceTimeout "{{user.persistence_timeout|0}}" \
  --HealthCheckConnectPort "{{user.health_check_port|0}}" \
  --HealthyThreshold "{{user.healthy_threshold|3}}" \
  --UnhealthyThreshold "{{user.unhealthy_threshold|3}}" \
  --HealthCheckTimeout "{{user.health_check_timeout|5}}" \
  --HealthCheckInterval "{{user.health_check_interval|2}}"
```

> **Note:** UDP listeners do not support layer-7 features (sticky sessions by cookie,
> X-Forwarded-For, etc.). Health check uses UDP packets.

#### Post-execution Validation

Verify listener appears in DescribeLoadBalancerListeners:

```bash
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerProtocol udp
```

---

### Operation: Describe Listeners

#### Execution — CLI

```bash
# Describe all listeners for an SLB
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "{{user.load_balancer_id}}"

# Filter by protocol
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerProtocol "{{user.listener_protocol}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Listener Port | `$.Listeners.Listener[].ListenerPort` | Frontend port |
| Protocol | `$.Listeners.Listener[].Protocol` | tcp / udp / http / https |
| Backend Server Port | `$.Listeners.Listener[].BackendServerPort` | Backend port |
| Bandwidth | `$.Listeners.Listener[].Bandwidth` | Mbps |
| Status | `$.Listeners.Listener[].Status` | running / stopped |
| Scheduler | `$.Listeners.Listener[].Scheduler` | wrr / rr |
| Health Check | `$.Listeners.Listener[].HealthCheck` | on / off |

---

### Operation: Start Listener

#### Pre-flight

- Verify listener exists and is currently `stopped`.

#### Execution — CLI

```bash
aliyun slb StartLoadBalancerListener \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}"
```

#### Post-execution Validation

Verify listener status is `running`:

```bash
for i in $(seq 1 12); do
  STATUS=$(aliyun slb DescribeLoadBalancerListeners \
    --LoadBalancerId "{{user.load_balancer_id}}" \
    --output cols=Status rows=Listeners.Listener[?ListenerPort=='{{user.listener_port}}'].Status)
  [ "$STATUS" = "running" ] && break
  sleep 5
done
```

---

### Operation: Stop Listener

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: stopping listener on port
  `{{user.listener_port}}` will halt traffic forwarding.

#### Execution — CLI

```bash
aliyun slb StopLoadBalancerListener \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}"
```

#### Post-execution Validation

Verify listener status is `stopped`:

```bash
for i in $(seq 1 12); do
  STATUS=$(aliyun slb DescribeLoadBalancerListeners \
    --LoadBalancerId "{{user.load_balancer_id}}" \
    --output cols=Status rows=Listeners.Listener[?ListenerPort=='{{user.listener_port}}'].Status)
  [ "$STATUS" = "stopped" ] && break
  sleep 5
done
```

---

### Operation: Delete Listener

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation: deleting listener on port
  `{{user.listener_port}}` will stop traffic forwarding.

#### Execution — CLI

```bash
aliyun slb DeleteLoadBalancerListener \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}"
```

#### Post-execution Validation

Verify listener no longer appears in DescribeLoadBalancerListeners.

---

### Operation: Create VServer Group

#### Pre-flight

- Verify SLB instance exists.
- Verify backend servers exist and are in the same region/VPC.

#### Execution — CLI

```bash
aliyun slb CreateVServerGroup \
  --RegionId "{{user.region}}" \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --VServerGroupName "{{user.vserver_group_name}}" \
  --BackendServers '[{"ServerId":"{{user.backend_server_id}}","Weight":"100","Type":"ecs","Port":"80"}]' \
  --ClientToken "{{output.client_token}}"
```

> **Note:** `BackendServers` is a JSON array string. Each element has:
> - `ServerId`: ECS/ENI/ECI instance ID
> - `Weight`: 0-100 (default 100)
> - `Type`: ecs (default), eni, eci
> - `Port`: backend port
> - `Description`: optional

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Read `{{output.vserver_group_id}}` from `$.VServerGroupId`.
2. Verify via DescribeVServerGroupAttribute:

```bash
aliyun slb DescribeVServerGroupAttribute \
  --VServerGroupId "{{output.vserver_group_id}}"
```

---

### Operation: Describe VServer Groups

#### Execution — CLI

```bash
aliyun slb DescribeVServerGroups \
  --LoadBalancerId "{{user.load_balancer_id}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| VServer Group ID | `$.VServerGroups.VServerGroup[].VServerGroupId` | Plain text |
| Name | `$.VServerGroups.VServerGroup[].VServerGroupName` | Plain text |

---

### Operation: Describe VServer Group Attribute

#### Execution — CLI

```bash
aliyun slb DescribeVServerGroupAttribute \
  --VServerGroupId "{{user.vserver_group_id}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Group ID | `$.VServerGroupId` | Plain text |
| Name | `$.VServerGroupName` | Plain text |
| Backend Server ID | `$.BackendServers.BackendServer[].ServerId` | Instance ID |
| Weight | `$.BackendServers.BackendServer[].Weight` | 0-100 |
| Type | `$.BackendServers.BackendServer[].Type` | ecs / eni / eci |
| Port | `$.BackendServers.BackendServer[].Port` | Backend port |
| Description | `$.BackendServers.BackendServer[].Description` | Plain text |

---

### Operation: Add Backend Servers to VServer Group

#### Execution — CLI

```bash
aliyun slb AddVServerGroupBackendServers \
  --VServerGroupId "{{user.vserver_group_id}}" \
  --BackendServers '[{"ServerId":"{{user.backend_server_id}}","Weight":"100","Type":"ecs","Port":"80"}]'
```

---

### Operation: Remove Backend Servers from VServer Group

#### Pre-flight (Safety Gate)

- **MUST** warn user that removing backend servers will stop traffic to those servers.

#### Execution — CLI

```bash
aliyun slb RemoveVServerGroupBackendServers \
  --VServerGroupId "{{user.vserver_group_id}}" \
  --BackendServers '[{"ServerId":"{{user.backend_server_id}}","Port":"80"}]'
```

> **Note:** For removal, only `ServerId` and `Port` are required in the JSON array.

---

### Operation: Delete VServer Group

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- Verify vserver group is not referenced by any listener or forwarding rule.

#### Execution — CLI

```bash
aliyun slb DeleteVServerGroup \
  --VServerGroupId "{{user.vserver_group_id}}"
```

---

### Operation: Add Backend Servers to Default Group

#### Pre-flight

- Verify SLB instance exists.
- Verify backend servers exist and are in the same region/VPC.

#### Execution — CLI

```bash
aliyun slb AddBackendServers \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --BackendServers '[{"ServerId":"{{user.backend_server_id}}","Weight":"100"}]'
```

> **Note:** Default group backend servers use the listener's `BackendServerPort`.
> For custom ports per backend, use VServer Groups instead.

---

### Operation: Remove Backend Servers from Default Group

#### Pre-flight (Safety Gate)

- **MUST** warn user that removing backend servers will stop traffic to those servers.

#### Execution — CLI

```bash
aliyun slb RemoveBackendServers \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --BackendServers '["{{user.backend_server_id}}"]'
```

---

### Operation: Set Backend Server Weights (Default Group)

#### Pre-flight

- Verify SLB instance exists.
- Verify backend server is in the default group.

#### Execution — CLI

```bash
aliyun slb SetBackendServers \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --BackendServers '[{"ServerId":"{{user.backend_server_id}}","Weight":"{{user.weight|100}}"}]'
```

> **Note:** Weight 0 means no traffic; 100 means full weight.

---

### Operation: Describe Health Status

#### Execution — CLI

```bash
aliyun slb DescribeHealthStatus \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Backend Server ID | `$.BackendServers.BackendServer[].ServerId` | Instance ID |
| Port | `$.BackendServers.BackendServer[].Port` | Backend port |
| Health Status | `$.BackendServers.BackendServer[].HealthStatus` | normal / abnormal |

---

### Operation: Upload Server Certificate

#### Pre-flight

- Verify certificate content is valid PEM format.
- Verify private key is valid PEM format (if uploading together).

#### Execution — CLI

```bash
aliyun slb UploadServerCertificate \
  --RegionId "{{user.region}}" \
  --ServerCertificateName "{{user.certificate_name}}" \
  --ServerCertificate "{{user.certificate_content}}" \
  --PrivateKey "{{user.private_key_content}}"
```

> **Security Warning:** Certificate content and private key are sensitive. Pass them
> via environment variables or secure means. NEVER log the private key.

#### Execution — JIT Go SDK

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Post-execution Validation

1. Read `{{output.certificate_id}}` from `$.ServerCertificateId`.
2. Verify via DescribeServerCertificates:

```bash
aliyun slb DescribeServerCertificates \
  --RegionId "{{user.region}}" \
  --ServerCertificateId "{{output.certificate_id}}"
```

---

### Operation: Describe Server Certificates

#### Execution — CLI

```bash
aliyun slb DescribeServerCertificates --RegionId "{{user.region}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Certificate ID | `$.ServerCertificates.ServerCertificate[].ServerCertificateId` | Plain text |
| Name | `$.ServerCertificates.ServerCertificate[].ServerCertificateName` | Plain text |
| Fingerprint | `$.ServerCertificates.ServerCertificate[].Fingerprint` | SHA-1 fingerprint |
| Common Name | `$.ServerCertificates.ServerCertificate[].CommonName` | CN field |
| Expire Time | `$.ServerCertificates.ServerCertificate[].ExpireTime` | ISO 8601 |
| Create Time | `$.ServerCertificates.ServerCertificate[].CreateTime` | ISO 8601 |

---

### Operation: Delete Server Certificate

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- Verify certificate is not referenced by any HTTPS listener.

#### Execution — CLI

```bash
aliyun slb DeleteServerCertificate \
  --ServerCertificateId "{{user.certificate_id}}"
```

---

### Operation: Create Access Control List

#### Execution — CLI

```bash
aliyun slb CreateAccessControlList \
  --RegionId "{{user.region}}" \
  --AclName "{{user.acl_name}}"
```

#### Post-execution Validation

1. Read `{{output.acl_id}}` from `$.AclId`.
2. Verify via DescribeAccessControlLists.

---

### Operation: Add ACL Entries

#### Execution — CLI

```bash
aliyun slb AddAccessControlListEntry \
  --AclId "{{user.acl_id}}" \
  --AclEntrys '[{"entry":"10.0.0.0/8","comment":"office-network"},{"entry":"192.168.0.0/16","comment":"vpc-network"}]'
```

> **Note:** `AclEntrys` is a JSON array string with `entry` (IP or CIDR) and
> optional `comment` fields.

---

### Operation: Describe Access Control Lists

#### Execution — CLI

```bash
aliyun slb DescribeAccessControlLists --RegionId "{{user.region}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| ACL ID | `$.Acls.Acl[].AclId` | Plain text |
| Name | `$.Acls.Acl[].AclName` | Plain text |
| Entry Count | `$.Acls.Acl[].AclEntryCount` | Number of entries |

---

### Operation: Delete Access Control List

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- Verify ACL is not referenced by any listener.

#### Execution — CLI

```bash
aliyun slb DeleteAccessControlList \
  --AclId "{{user.acl_id}}"
```

---

### Operation: Create Forwarding Rules

#### Pre-flight

- Verify SLB instance and listener exist.
- Verify vserver group exists (if routing to vserver group).

#### Execution — CLI

```bash
aliyun slb CreateRules \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}" \
  --RuleList '[{"RuleName":"rule1","Domain":"example.com","Url":"/api/*","VServerGroupId":"{{user.vserver_group_id}}"}]' \
  --ClientToken "{{output.client_token}}"
```

> **Note:** `RuleList` is a JSON array string. Each rule has `RuleName`, `Domain`,
> `Url`, and `VServerGroupId`.

#### Post-execution Validation

1. Read `{{output.rule_ids}}` from `$.Rules.Rule[].RuleId`.
2. Verify via DescribeRules:

```bash
aliyun slb DescribeRules \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}"
```

---

### Operation: Describe Rules

#### Execution — CLI

```bash
aliyun slb DescribeRules \
  --LoadBalancerId "{{user.load_balancer_id}}" \
  --ListenerPort "{{user.listener_port}}"
```

#### Present to User

| Field | Path | Notes |
|-------|------|-------|
| Rule ID | `$.Rules.Rule[].RuleId` | Plain text |
| Name | `$.Rules.Rule[].RuleName` | Plain text |
| Domain | `$.Rules.Rule[].Domain` | Matched domain |
| URL | `$.Rules.Rule[].Url` | Matched URL pattern |
| VServer Group ID | `$.Rules.Rule[].VServerGroupId` | Target group |

---

### Operation: Delete Rules

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.

#### Execution — CLI

```bash
aliyun slb DeleteRules \
  --RuleIds '["{{user.rule_id}}"]'
```

---

---

### Operation: Intelligent Inspection（智能巡检）

详见 [智能巡检](references/intelligent-inspection.md)

## Failure Recovery (Global)

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `InvalidParameter` / 400 | 0–1 | — | Fix args from OpenAPI; retry once if safe |
| `QuotaExceeded` | 0 | — | HALT |
| `InsufficientBalance` | 0 | — | HALT |
| `ResourceAlreadyExists` | 0 | — | Ask reuse vs new name |
| Throttling / 429 / `Throttling` | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |
| `LoadBalancerNotFound` / `ResourceNotFound` | 0 | — | Verify resource ID; HALT if truly missing |
| `ListenerAlreadyExists` | 0 | — | Ask user to use different port or modify existing |
| `CertificateNotFound` | 0 | — | Verify certificate ID; suggest upload |
| `AclNotFound` | 0 | — | Verify ACL ID; suggest create |
| `VServerGroupNotFound` | 0 | — | Verify group ID; suggest create |

## Prerequisites

见 [执行环境配置](../alicloud-skill-generator/references/execution-environment.md)

---

## Well-Architected Assessment

Evaluated per Alibaba Cloud [Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

| Pillar | Key Guidance |
|--------|-------------|
| **Security** | IAM: `slb:Describe*`, `slb:Create*`. Intranet SLB for internal traffic. ACLs for access control. Always HTTPS for public-facing, regular cert rotation |
| **Stability** | Multi-AZ. Health checks per backend. Monitor 5xx, ActiveConnection, QPS. Failover to backup listener group, RTO < 1min (DNS TTL) |
| **Cost** | PayBySpecification for stable traffic, PayByCLCU for variable. Delete idle LBs (no backend, no connections for 7d). Over-provisioned specs → downgrade |
| **Efficiency** | Auto-scaling with ECS ASG. Terraform IaC support. JSON output for CI/CD |
| **Performance** | ActiveConnection > 80% scale up, < 30% down. QPS > 80% rated alert. Health check interval ≤ 5s for production |

## Reference Directory

- [Core Concepts](references/core-concepts.md) — SLB/CLB product concepts, key terminology, quotas, and limits
- [API & SDK Usage](references/api-sdk-usage.md) — Complete API/SDK operations map, request/response notes
- [CLI Usage](references/cli-usage.md) — `aliyun slb` command reference with examples for all operations
- [Prompt Examples](references/prompt-examples.md) — Ready-to-use prompt templates for common scenarios, copy-paste to interact with the skill
- [Troubleshooting Guide](references/troubleshooting.md) — Common errors, diagnostic order, RAM policies
- [Monitoring & Alerts](references/monitoring.md) — CloudMonitor metrics, health checks, alert recommendations
- [Integration](references/integration.md) — Environment setup, JIT Go SDK bootstrap, cross-product integration
- [Batch Operations](../alicloud-ecs-ops/references/idle-resource-detection.md) — 批量并行操作模板 (See: ../alicloud-skill-generator/templates/batch-operations.md)

### API 调用计数

See: [../alicloud-skill-generator/references/api-call-counter.md](../alicloud-skill-generator/references/api-call-counter.md)

### Assets

The `assets/` directory contains reusable configuration templates and examples:

- `assets/slb-instance-template.json` — Example SLB instance creation payload
- `assets/listener-config-examples/` — Protocol-specific listener configuration examples
- `assets/ram-policy.json` — Minimal RAM policy for SLB operations

## Operational Best Practices

- **Least privilege:** RAM policies scoped to required SLB APIs only.
- **Availability:** Use multi-AZ deployment for SLB instances.
- **Security:** Enable deletion protection for production SLB instances.
- **Cost:** Use pay-by-traffic for variable workloads; right-size instance specs.
- **Health checks:** Configure appropriate health check intervals and thresholds.
- **Session persistence:** Use only when required; prefer stateless application design.
- **HTTPS:** Always use HTTPS listeners for public-facing services; upload valid certificates.
- **ACLs:** Restrict access using ACLs for sensitive services.

---

## Quality Gate (GCL)

Phase 5 rollout for `recommended` skills per [`AGENTS.md` §12](../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Recommended** (Phase 5, `max_iter=3`) |
| Most-scrutinized | `DeleteLoadBalancer` (cascade: listeners + backends + EIP), `RemoveVServerGroupBackendServers` (≥ 1 healthy) |
| Cross-skill delegation | EIP → `alicloud-eip-ops` GCL |

### Changelog
1.0.0 | 2026-06-04 | Phase 5 `recommended` rollout for slb-ops.

---

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.

- **[Code Snippets Rule](../alicloud-skill-generator/templates/code-snippets.md)** —
  When `cli_applicability: sdk-only` (CLI 不足以覆盖完整功能，必须依赖 SDK/API 方式),
  the skill MUST provide `assets/code-snippets/` with runnable Go SDK code.
  **DOES NOT APPLY** — 本 skill 为 `cli-first`，CLI/SDK 已覆盖，无需 code snippets.
