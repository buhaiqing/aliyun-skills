---
name: alicloud-slb-ops
description: >-
  Use when you need to deploy, configure, troubleshoot, or monitor Alibaba Cloud
  SLB (Classic Load Balancer / CLB) instances, listeners, virtual server groups,
  backend servers, certificates, access control lists, or forwarding rules via
  official `aliyun` CLI or JIT Go SDK; user mentions SLB, CLB, 负载均衡,
  传统型负载均衡, Classic Load Balancer, or tasks target SLB instances/listeners/
  vserver groups/certificates/ACLs.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-05-14"
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

> **Security Warning:** **NEVER** log, print, or expose `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
> (or any secret) in console output, debug messages, or logs. When verification is
> needed, check existence only without printing the actual value. If logging
> credential status is required, use masked placeholders like
> `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>` or `ALIBABA_CLOUD_ACCESS_KEY_SECRET=***`.
> This applies to all execution flows (SDK, CLI, and debugging scripts).

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

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-14 | Initial SLB skill with cli-first (CLI + SDK fallback) support |

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

```go
package main

import (
	"fmt"
	"os"
	"time"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	slb "github.com/alibabacloud-go/slb-20140515/v2/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	c, err := slb.NewClient(config)
	if err != nil {
		panic(err)
	}

	req := &slb.CreateLoadBalancerRequest{
		RegionId:         tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
		LoadBalancerName: tea.String(os.Getenv("LOAD_BALANCER_NAME")),
		AddressType:      tea.String(os.Getenv("ADDRESS_TYPE")),
		VpcId:            tea.String(os.Getenv("VPC_ID")),
		VSwitchId:        tea.String(os.Getenv("VSWITCH_ID")),
		Bandwidth:        tea.Int32(int32(bandwidthInt)),
		LoadBalancerSpec: tea.String(os.Getenv("LOAD_BALANCER_SPEC")),
	}

	resp, err := c.CreateLoadBalancer(req)
	if err != nil {
		panic(err)
	}

	lbId := tea.ToString(resp.Body.LoadBalancerId)
	fmt.Printf("Created SLB: %s\n", lbId)

	// Poll until active
	for i := 0; i < 24; i++ {
		descReq := &slb.DescribeLoadBalancerAttributeRequest{
			LoadBalancerId: tea.String(lbId),
		}
		descResp, err := c.DescribeLoadBalancerAttribute(descReq)
		if err != nil {
			panic(err)
		}
		if tea.ToString(descResp.Body.LoadBalancerStatus) == "active" {
			fmt.Println("SLB is active")
			break
		}
		time.Sleep(5 * time.Second)
	}
}
```

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

```go
req := &slb.DescribeLoadBalancersRequest{
	RegionId:       tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	LoadBalancerId: tea.String(os.Getenv("LOAD_BALANCER_ID")),
}
resp, err := c.DescribeLoadBalancers(req)
```

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

```go
req := &slb.CreateLoadBalancerTCPListenerRequest{
	LoadBalancerId:     tea.String(os.Getenv("LOAD_BALANCER_ID")),
	ListenerPort:       tea.Int32(int32(listenerPortInt)),
	BackendServerPort:  tea.Int32(int32(backendPortInt)),
	Bandwidth:          tea.Int32(int32(bandwidthInt)),
	Scheduler:          tea.String(os.Getenv("SCHEDULER")),
	HealthCheckType:    tea.String(os.Getenv("HEALTH_CHECK_TYPE")),
	PersistenceTimeout: tea.Int32(int32(persistenceInt)),
}
resp, err := c.CreateLoadBalancerTCPListener(req)
```

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

```go
req := &slb.CreateLoadBalancerHTTPListenerRequest{
	LoadBalancerId:    tea.String(os.Getenv("LOAD_BALANCER_ID")),
	ListenerPort:      tea.Int32(int32(listenerPortInt)),
	BackendServerPort: tea.Int32(int32(backendPortInt)),
	Bandwidth:         tea.Int32(int32(bandwidthInt)),
	Scheduler:         tea.String(os.Getenv("SCHEDULER")),
	StickySession:     tea.String(os.Getenv("STICKY_SESSION")),
	HealthCheck:       tea.String(os.Getenv("HEALTH_CHECK")),
	XForwardedFor:     tea.String(os.Getenv("X_FORWARDED_FOR")),
}
resp, err := c.CreateLoadBalancerHTTPListener(req)
```

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

```go
req := &slb.CreateVServerGroupRequest{
	RegionId:         tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	LoadBalancerId:   tea.String(os.Getenv("LOAD_BALANCER_ID")),
	VServerGroupName: tea.String(os.Getenv("VSERVER_GROUP_NAME")),
	BackendServers:   tea.String(os.Getenv("BACKEND_SERVERS")),
}
resp, err := c.CreateVServerGroup(req)
```

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

```go
req := &slb.UploadServerCertificateRequest{
	RegionId:              tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	ServerCertificateName: tea.String(os.Getenv("CERTIFICATE_NAME")),
	ServerCertificate:     tea.String(os.Getenv("CERTIFICATE_CONTENT")),
	PrivateKey:            tea.String(os.Getenv("PRIVATE_KEY_CONTENT")),
}
resp, err := c.UploadServerCertificate(req)
```

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

一键执行SLB实例的全面健康检查，整合实例状态 + 监听状态 + 后端健康 + CMS指标。

#### 执行流程

1. 调用 `DescribeLoadBalancerAttribute` 检查实例状态
2. 调用 `DescribeLoadBalancerListeners` 检查所有监听状态
3. 调用 `DescribeHealthStatus` 检查所有后端服务器健康状态
4. 调用 `alicloud-cms-ops` 查询最近15分钟的丢包/延迟/5xx指标
5. 检查证书过期时间（如有HTTPS监听）
6. 综合评分并生成巡检报告

#### 巡检评分标准

| 维度 | 评分依据 | 权重 |
|------|---------|------|
| 实例状态 | active=100, 其他=0 | 20% |
| 监听状态 | 全部running=100, 部分异常=50, 全部异常=0 | 20% |
| 后端健康比例 | 100%=100, >80%=60, <80%=0 | 25% |
| 丢包率 | 0%=100, <1%=60, >1%=0 | 15% |
| 5xx错误率 | 0%=100, <1%=60, >1%=0 | 10% |
| 证书有效期 | >30天=100, 7-30天=60, <7天=0 | 10% |

#### 执行 — CLI

```bash
#!/bin/bash
# slb-intelligent-inspection.sh
# Usage: ./slb-intelligent-inspection.sh <LoadBalancerId> <RegionId>

LB_ID="$1"
REGION="$2"
SCORE=0

echo "=== SLB Intelligent Inspection ==="
echo "Load Balancer: $LB_ID"
echo "Region: $REGION"
echo ""

# 1. Instance status check
STATUS=$(aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId "$LB_ID" \
  --output cols=LoadBalancerStatus rows=LoadBalancerStatus)
echo "[1/6] Instance Status: $STATUS"
[ "$STATUS" = "active" ] && SCORE=$((SCORE + 20))

# 2. Listener status check
LISTENERS=$(aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "$LB_ID" \
  --output cols=Status rows=Listeners.Listener[].Status 2>/dev/null)
LISTENER_OK=$(echo "$LISTENERS" | grep -c "running" || true)
LISTENER_TOTAL=$(echo "$LISTENERS" | wc -l | tr -d ' ')
echo "[2/6] Listeners Running: $LISTENER_OK/$LISTENER_TOTAL"
if [ "$LISTENER_TOTAL" -gt 0 ]; then
  [ "$LISTENER_OK" -eq "$LISTENER_TOTAL" ] && SCORE=$((SCORE + 20))
  [ "$LISTENER_OK" -gt 0 ] && [ "$LISTENER_OK" -lt "$LISTENER_TOTAL" ] && SCORE=$((SCORE + 10))
fi

# 3. Backend health check (iterate all listeners)
echo "[3/6] Backend Health:"
PORTS=$(aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "$LB_ID" \
  --output cols=ListenerPort rows=Listeners.Listener[].ListenerPort 2>/dev/null)
ALL_HEALTHY=0
ALL_TOTAL=0
for port in $PORTS; do
  HEALTH=$(aliyun slb DescribeHealthStatus \
    --LoadBalancerId "$LB_ID" \
    --ListenerPort "$port" \
    --output cols=HealthStatus rows=BackendServers.BackendServer[].HealthStatus 2>/dev/null)
  PORT_HEALTHY=$(echo "$HEALTH" | grep -c "normal" || true)
  PORT_TOTAL=$(echo "$HEALTH" | wc -l | tr -d ' ')
  if [ "$PORT_TOTAL" -gt 0 ]; then
    ALL_HEALTHY=$((ALL_HEALTHY + PORT_HEALTHY))
    ALL_TOTAL=$((ALL_TOTAL + PORT_TOTAL))
    echo "  Port $port: $PORT_HEALTHY/$PORT_TOTAL healthy"
  fi
done
if [ "$ALL_TOTAL" -gt 0 ]; then
  HEALTH_RATIO=$((ALL_HEALTHY * 100 / ALL_TOTAL))
  [ "$HEALTH_RATIO" -eq 100 ] && SCORE=$((SCORE + 25))
  [ "$HEALTH_RATIO" -ge 80 ] && [ "$HEALTH_RATIO" -lt 100 ] && SCORE=$((SCORE + 15))
else
  echo "  No backends configured"
fi

# 4. Certificate expiry check
echo "[4/6] Certificate Check:"
CERT_IDS=$(aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId "$LB_ID" \
  --output cols=ListenerPort,Protocol rows=Listeners.Listener[].{ListenerPort,Protocol} 2>/dev/null | grep -i "https" || true)
if [ -n "$CERT_IDS" ]; then
  aliyun slb DescribeServerCertificates \
    --RegionId "$REGION" \
    --output cols=ServerCertificateName,CommonName,ExpireTime \
    rows=ServerCertificates.ServerCertificate[].{ServerCertificateName,CommonName,ExpireTime} 2>/dev/null || echo "  No certificates found"
else
  echo "  No HTTPS listeners configured"
fi

# 5. CMS metrics (drop rate, 5xx)
echo "[5/6] CMS Metrics:"
START_TIME=$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
aliyun cms DescribeMetricList \
  --Namespace acs_slb \
  --MetricName InstanceDropConnection \
  --Dimensions "[{\"instanceId\":\"$LB_ID\"}]" \
  --Period 60 \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" 2>/dev/null || echo "  Metrics N/A"

echo ""
echo "=== Inspection Score: $SCORE/100 ==="
if [ "$SCORE" -ge 80 ]; then
  echo "Status: HEALTHY"
elif [ "$SCORE" -ge 60 ]; then
  echo "Status: WARNING - Review recommended"
else
  echo "Status: CRITICAL - Immediate action required"
fi
```

#### 输出格式

```json
{
  "inspection_time": "2026-05-14T10:00:00Z",
  "resource_type": "slb",
  "resource_id": "lb-bp67acfmxazb4ph****",
  "overall_score": 85,
  "dimensions": [
    {"name": "实例状态", "score": 100, "status": "healthy"},
    {"name": "监听状态", "score": 100, "status": "healthy", "value": "3/3 running"},
    {"name": "后端健康比例", "score": 100, "status": "healthy", "value": "4/4"},
    {"name": "丢包率", "score": 100, "status": "healthy", "value": "0"},
    {"name": "5xx错误率", "score": 60, "status": "warning", "value": "0.5%"},
    {"name": "证书有效期", "score": 100, "status": "healthy", "value": ">30天"}
  ],
  "recommendations": [
    "5xx错误率0.5%超过警告阈值，建议检查后端服务器健康状态"
  ]
}
```

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

1. **Install `aliyun` CLI** (primary execution path — static Go binary, no runtime dependencies):

   ```bash
   # Official installer (auto-detects OS and architecture)
   /bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"

   # Or Homebrew (macOS)
   brew install aliyun-cli
   ```

2. **Bootstrap Go runtime** (for JIT SDK fallback — only needed if CLI does not support operation):

   ```bash
   # Check if Go exists
   if ! command -v go &> /dev/null; then
       # JIT download Go 1.24 (auto-detects OS and architecture)
       OS=$(uname -s | tr '[:upper:]' '[:lower:]')
       ARCH=$(uname -m)
       [ "$ARCH" = "x86_64" ] && ARCH="amd64"
       [ "$ARCH" = "aarch64" ] && ARCH="arm64"

       mkdir -p /tmp/go-runtime
       curl -fsSL "https://go.dev/dl/go1.24.0.${OS}-${ARCH}.tar.gz" | tar -xz -C /tmp/go-runtime

       # Set environment variables
       export PATH="/tmp/go-runtime/go/bin:$PATH"
       export GOPATH="/tmp/go-workspace"
       export GOCACHE="/tmp/go-cache"
       export GOMODCACHE="/tmp/go-modcache"
       export GOPROXY="https://goproxy.cn,direct"  # China CDN mirror
   fi

   go version
   ```

   > Go version strategy: **JIT download Go 1.24+**, **Script compatibility Go 1.21+** (minimum).

3. **Configure Credentials** — Environment variables (recommended for Agent execution):

   ```bash
   export ALIBABA_CLOUD_ACCESS_KEY_ID="{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}"
   export ALIBABA_CLOUD_REGION_ID="{{env.ALIBABA_CLOUD_REGION_ID}}"
   ```

   **Alternative — Interactive CLI Configuration:**
   ```bash
   aliyun configure
   ```

   **Alternative — Config File (`~/.aliyun/config.json`):**
   ```bash
   mkdir -p ~/.aliyun
   cat > ~/.aliyun/config.json << 'CONFIGEOF'
   {
     "current": "default",
     "profiles": [
       {
         "name": "default",
         "mode": "AK",
         "access_key_id": "{{user.access_key_id}}",
         "access_key_secret": "{{user.access_key_secret}}",
         "region_id": "{{user.region}}"
       }
     ]
   }
   CONFIGEOF
   ```

4. **Verify Configuration**:
   ```bash
   # Quick validation (JSON output by default)
   aliyun slb DescribeRegions
   ```

> **Security:** Never commit `.env` to version control (already in `.gitignore`).
> All credentials use `{{env.*}}` placeholders in generated Skills — never real values.

## Reference Directory

- [Core Concepts](references/core-concepts.md) — SLB/CLB product concepts, key terminology, quotas, and limits
- [API & SDK Usage](references/api-sdk-usage.md) — Complete API/SDK operations map, request/response notes
- [CLI Usage](references/cli-usage.md) — `aliyun slb` command reference with examples for all operations
- [Prompt Examples](references/prompt-examples.md) — Ready-to-use prompt templates for common scenarios, copy-paste to interact with the skill
- [Troubleshooting Guide](references/troubleshooting.md) — Common errors, diagnostic order, RAM policies
- [Monitoring & Alerts](references/monitoring.md) — CloudMonitor metrics, health checks, alert recommendations
- [Integration](references/integration.md) — Environment setup, JIT Go SDK bootstrap, cross-product integration

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
