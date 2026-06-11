---
name: alicloud-alb-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba Cloud ALB (Application Load Balancer, 应用型负载均衡/应用型实例) — ALB instance lifecycle, listeners, server groups, forwarding rules, ACLs, security policies, health check templates, AScript rules, and monitoring. User mentions ALB, 应用型负载均衡, Application Load Balancer, 应用型实例, or describes application-layer load balancing scenarios (HTTP/HTTPS routing, SSL offloading, WAF integration, canary deployment, server group management, listener configuration) even without naming the product explicitly. CLI: `aliyun alb`, SDK: `alb-2020-06-16`. NOT for CLB (Classic Load Balancer/SLB), NLB (Network Load Balancer), ECS/VPC networking only, DDoS mitigation, or billing/RAM-only tasks.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-07"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "ALB 2020-06-16 / https://help.aliyun.com/zh/alb/"
  cli_applicability: dual-path
  cli_support_evidence: "Confirmed via `aliyun help alb` — ALB (Application Load Balancer) is supported by the official aliyun CLI with full coverage of CRUD operations for instances, listeners, server groups, ACLs, rules, security policies, health check templates, and AScripts."
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
  gcl_classification: required
  gcl_max_iter: 2
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud ALB Operations Skill

## Common JSON Paths (Centralized)

```
# CreateLoadBalancer:        $.LoadBalancerId
# Describe/Get LB:           $.LoadBalancer.{Id,LoadBalancerStatus,Address,AddressType,DNSName}
# ListLoadBalancers:         $.LoadBalancers[].{LoadBalancerId,LoadBalancerStatus,Address}
# CreateListener:            $.ListenerId
# ListListeners:             $.Listeners[].{ListenerId,ListenerProtocol,ListenerPort}
# CreateServerGroup:         $.ServerGroupId
# ListServerGroups:          $.ServerGroups[].ServerGroupId
# AddServers:                $.JobId (async)
# ListServerGroupServers:    $.Servers[].{ServerId,ServerIp,Port,Weight}
# CreateAcl:                 $.AclId
# ListAcls:                  $.Acls[].AclId
# CreateRule:                $.RuleId
# ListRules:                 $.Rules[].RuleId
# CreateSecurityPolicy:      $.SecurityPolicyId
# ListSecurityPolicies:      $.SecurityPolicies[].SecurityPolicyId
# CreateHealthCheckTemplate: $.HealthCheckTemplateId
# ListHealthCheckTemplates:  $.HealthCheckTemplates[].HealthCheckTemplateId
# EnableDeletionProtection:  $.RequestId
# TagResources:              $.RequestId
```

## Overview

ALB is Alibaba Cloud's Layer 7 (HTTP/HTTPS/QUIC) load balancer. This skill is an **operational runbook** for agents: Pre-flight → Execute (CLI primary + SDK fallback) → Validate → Recover.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT Use conditions with precise triggers and delegation rules |
| 2 | **Structured I/O** | Placeholders (`{{env.*}}`, `{{user.*}}`, `{{output.*}}`) with type and source |
| 3 | **Explicit Actionable Steps** | Every operation: Pre-flight → Execute → Validate → Recover |
| 4 | **Complete Failure Strategies** | Error taxonomy with ≥ 10 product-specific codes; HALT vs retry |
| 5 | **Absolute Single Responsibility** | ALB instances, listeners, server groups, rules, ACLs, security policies; delegates CLB/NLB |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "ALB" OR "Application Load Balancer" OR "应用型负载均衡" OR "应用型实例"
- Task involves CRUD on **ALB instances** (create, describe, modify, delete, list, enable/disable deletion protection)
- Task involves **listeners** (create, describe, modify, delete, start, stop HTTP/HTTPS/QUIC listeners)
- Task involves **server groups** (create, describe, modify, delete, add/remove/replace servers)
- Task involves **forwarding rules** (create, describe, modify, delete single/batch rules)
- Task involves **ACLs** (create, describe, modify, delete, add/remove entries, associate/dissociate with listeners)
- Task involves **security policies** (create, describe, modify, delete custom policies)
- Task involves **health check templates** (create, describe, modify, delete, apply to server groups)
- Task involves **AScript rules** (create, describe, modify, delete scripts)
- Task involves **SSL/TLS certificates** (associate/dissociate additional certificates)
- Task involves **access logs** (enable/disable, update log config)
- Task involves **zones** (modify zones, shift zone DNS records)
- Task involves **tagging** (tag/untag resources, list tag keys/values)
- Task involves **security group association** (join/leave security groups)
- Task involves **IP address type configuration** (public/private IPv4/IPv6)
- Task involves **monitoring, health checks, or traffic routing diagnostics**
- User asks to deploy, configure, troubleshoot, or monitor ALB

### SHOULD NOT Use This Skill When

- Task is purely billing / account management → delegate to billing skill
- Task is RAM / permission model only → delegate to: `alicloud-ram-ops`
- Task is about **CLB/SLB (Classic Load Balancer)** → delegate to: `alicloud-slb-ops`
- Task is about **NLB (Network Load Balancer)** → NLB uses a separate skill when present
- Task is about **ECS / VPC only** → delegate to respective skills
- User insists on **console-only** flows

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |

## Variable Convention (Agent-Readable)

| Var | Source | Action |
|-----|--------|--------|
| `{{env.*}}` (3 vars) | Environment | NEVER ask; HALT if unset |
| `{{user.*}}` | User input | Ask once, reuse |
| — region, lb_id/name, vpc_id, vswitch_id, zone_id | | |
| — listener_id/port/protocol | | |
| — server_group_id/name, server_id/ip, acl_id | | |
| — rule_id, security_policy_id, hc_template_id | | |
| — certificate_id, ascrip_id | | |
| `{{output.*}}` | API/CLI response | Parse per OpenAPI path |
| — lb_id, listener_id, server_group_id | | |
| — acl_id, rule_id, request_id | | |

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for all paths, fields, enums, and response shapes.
- **ClientToken:** Generate UUID v4 for write operations for idempotency.
- **ALB uses asynchronous operations** for some APIs (CreateLoadBalancer, AddServersToServerGroup, etc.). Use ListAsynJobs to poll job status.
- **Timestamps:** ISO 8601 format.

### Expected State Transitions

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| CreateLoadBalancer | — | `Active` | 10s | 600s |
| UpdateLoadBalancerAttribute | any stable | target state | 5s | 120s |
| DeleteLoadBalancer | any stable | absent | 5s | 300s |
| CreateListener | — | active | 5s | 120s |
| StartListener | Inactive | active | 5s | 60s |
| StopListener | Active | Inactive | 5s | 60s |
| CreateServerGroup | — | active | 5s | 60s |
| AddServersToServerGroup | — | active (async job) | 5s | 120s |
| CreateRule | — | active | 5s | 60s |
| CreateAcl | — | active | 5s | 60s |

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-07 | Initial ALB skill with dual-path (CLI + SDK) support, GCL required |

## Quick Start

### Prerequisites
- [ ] `aliyun` CLI installed
- [ ] Credentials: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- [ ] Region: `ALIBABA_CLOUD_REGION_ID`

### First Command
```bash
# List all ALB instances in region
aliyun alb ListLoadBalancers --RegionId "{{env.ALIBABA_CLOUD_REGION_ID}}"
```

### Capabilities at a Glance

| Operation | Description | Risk |
|-----------|-------------|------|
| CreateLoadBalancer | Create ALB instance | Low |
| DeleteLoadBalancer | Delete ALB instance | **High** |
| UpdateLoadBalancerAttribute | Modify ALB attributes | Medium |
| CreateListener | Create listener | Low |
| DeleteListener | Delete listener | Medium |
| StartListener / StopListener | Enable/disable listener | Low |
| CreateServerGroup | Create server group | Low |
| DeleteServerGroup | Delete server group | Medium |
| AddServersToServerGroup | Add backend servers | Low |
| RemoveServersFromServerGroup | Remove backend servers | Medium |
| CreateRule | Create forwarding rule | Low |
| DeleteRule | Delete forwarding rule | Medium |
| CreateAcl | Create ACL | Low |
| DeleteAcl | Delete ACL | Medium |
| CreateSecurityPolicy | Create security policy | Low |
| DeleteSecurityPolicy | Delete security policy | Low |
| CreateHealthCheckTemplate | Create health check template | Low |
| DeleteHealthCheckTemplates | Delete health check templates | Low |
| EnableDeletionProtection | Enable deletion protection | Low |
| UpdateLoadBalancerEdition | Upgrade ALB edition | Medium |
| TagResources / UnTagResources | Manage tags | Low |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI + SDK) → Validate → Recover**.

---

### Operation: Create ALB Instance

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI | `aliyun version` | Exit code 0 | Document CLI install |
| Credentials | Env vars or CLI config | Non-empty keys | HALT; user configures |
| Region | `aliyun alb DescribeRegions` | `{{user.region}}` supported | Suggest valid region |
| Zones | `aliyun alb DescribeZones --RegionId "{{user.region}}"` | Zones available | Suggest valid zone |
| VPC/VSwitch | `aliyun vpc DescribeVpcs/DescribeVSwitches` | Exist in region | Delegate to `alicloud-vpc-ops` |
| Bandwidth | `aliyun vpc DescribeCommonBandwidthPackages` (for shared) | For internet type | Delegate to bandwidth management |

#### Execution — CLI (Primary Path)

```bash
# Create private ALB (intranet)
aliyun alb CreateLoadBalancer \
  --RegionId "{{user.region}}" \
  --LoadBalancerName "{{user.lb_name}}" \
  --AddressType Intranet \
  --VpcId "{{user.vpc_id}}" \
  --ZoneMappings "[{\"VSwitchId\":\"{{user.vswitch_id}}\"}]" \
  --LoadBalancerEdition "{{user.lb_edition|Basic}}" \
  --ClientToken "{{output.client_token}}"
```

> **Output:** Parse `LoadBalancerId` from JSON response. LB creation is async — poll with ListAsynJobs.
> Full command variants (public ALB, bandwidth package) at [references/cli-usage.md](references/cli-usage.md).

#### Execution — JIT Go SDK (Fallback Path)

See [`references/api-sdk-usage.md`](references/api-sdk-usage.md) for full SDK operation map and Go template.

```go
// go get github.com/alibabacloud-go/alb-20200616/v2/client
request := &alb.CreateLoadBalancerRequest{
    RegionId:          tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    LoadBalancerName:  tea.String(os.Getenv("LB_NAME")),
    AddressType:       tea.String("Intranet"),
    VpcId:             tea.String(os.Getenv("VPC_ID")),
    ZoneMappings: []*alb.CreateLoadBalancerRequestZoneMappings{
        {VSwitchId: tea.String(os.Getenv("VSWITCH_ID"))},
    },
    LoadBalancerEdition: tea.String("Basic"),
}
response, err := client.CreateLoadBalancer(request)
```

#### Post-execution Validation

1. Capture `{{output.lb_id}}` from `$.LoadBalancerId`.
2. Poll job status via `ListAsynJobs` until complete:
   ```bash
   aliyun alb ListAsynJobs --ResourceType LoadBalancer --ResourceIds "[\"{{output.lb_id}}\"]" --RegionId "{{user.region}}"
   ```
3. On API-level completion, verify `GetLoadBalancerAttribute` returns `LoadBalancerStatus == Active`.
4. On success, report `{{output.lb_id}}`, Address, and DNSName.
5. On failure, check job status error message.

#### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| InvalidParameter / 400 | 0-1 | — | Fix args from OpenAPI; retry once |
| QuotaExceeded.ALB | 0 | — | HALT — request quota increase |
| InsufficientBalance | 0 | — | HALT — recharge account |
| ZoneNotSupported | 0 | — | Suggest valid zones from DescribeZones |
| Throttling / 429 | 3 | exponential | Back off; respect Retry-After |
| InternalError / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |

---

### Operation: Describe/Get Load Balancer

#### Execution — CLI

```bash
# Get ALB instance details
aliyun alb GetLoadBalancerAttribute --LoadBalancerId "{{user.lb_id}}"

# List all ALB instances in region
aliyun alb ListLoadBalancers --RegionId "{{user.region}}"
```

> Full field extraction examples at [references/cli-usage.md](references/cli-usage.md).

---

### Operation: Update Load Balancer Attribute

#### Pre-flight
- Verify ALB exists; check `ModificationProtectionStatus`.

#### Execution — CLI

```bash
# Update ALB name
aliyun alb UpdateLoadBalancerAttribute \
  --LoadBalancerId "{{user.lb_id}}" \
  --LoadBalancerName "{{user.new_lb_name}}"

# Enable/disable deletion protection
aliyun alb EnableDeletionProtection --ResourceId "{{user.lb_id}}" --RegionId "{{user.region}}"
aliyun alb DisableDeletionProtection --ResourceId "{{user.lb_id}}" --RegionId "{{user.region}}"
```

> Full update operations (address type, zones, edition) at [references/cli-usage.md](references/cli-usage.md).

---

### Operation: Create Listener

#### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| ALB exists | `GetLoadBalancerAttribute` | Active | HALT |
| Port available | `ListListeners` | Port not used | Suggest different port |
| Certificate | (for HTTPS) Verify cert exists | Uploaded | Delegate to certificate mgmt |

#### Execution — CLI

```bash
# Create HTTP listener
aliyun alb CreateListener \
  --ListenerProtocol HTTP \
  --ListenerPort "{{user.listener_port|80}}" \
  --LoadBalancerId "{{user.lb_id}}" \
  --DefaultActions "[{\\"Type\\":\\"ForwardGroup\\",\\"ForwardGroupConfig\\":{\\"ServerGroupTuples\\":[{\\"ServerGroupId\\":\\"{{user.server_group_id}}\\"}]}}]"
```

> Full examples (HTTPS with certs, QUIC) at [references/cli-usage.md](references/cli-usage.md).

#### Post-execution Validation

Capture `{{output.listener_id}}` from `$.ListenerId`. Verify via:
```bash
aliyun alb GetListenerAttribute --ListenerId "{{output.listener_id}}"
```

---

### Operation: Manage Server Group

#### Execution — CLI

```bash
# Create server group
aliyun alb CreateServerGroup \
  --ServerGroupName "{{user.server_group_name}}" \
  --VpcId "{{user.vpc_id}}" \
  --Protocol "{{user.server_group_protocol|HTTP}}" \
  --RegionId "{{user.region}}"

# Add backend servers
aliyun alb AddServersToServerGroup \
  --ServerGroupId "{{user.server_group_id}}" \
  --Servers "[{\\"ServerId\\":\\"{{user.server_id}}\\",\\"ServerIp\\":\\"{{user.server_ip}}\\",\\"ServerType\\":\\"Ecs\\",\\"Port\\":{{user.server_port}},\\"Weight\\":{{user.server_weight|100}}}]" \
  --RegionId "{{user.region}}"
```

> Full operations (remove servers, list servers, delete SG) at [references/cli-usage.md](references/cli-usage.md). Note: `AddServersToServerGroup` is async — poll `ListAsynJobs`.

---

### Operation: Create Forwarding Rule

#### Pre-flight

- Verify listener exists.
- Verify server group exists.

#### Execution — CLI

```bash
# Create a single forwarding rule
aliyun alb CreateRule \
  --ListenerId "{{user.listener_id}}" \
  --Priority "{{user.rule_priority|10}}" \
  --RuleConditions "[{\\"Type\\":\\"Host\\",\\"HostConfig\\":{\\"Values\\":[\\"{{user.host_name}}\\"]}}]" \
  --RuleActions "[{\\"Type\\":\\"ForwardGroup\\",\\"ForwardGroupConfig\\":{\\"ServerGroupTuples\\":[{\\"ServerGroupId\\":\\"{{user.server_group_id}}\\"}]},\\"Order\\":1}]"
```

> Batch create (CreateRules) at [references/cli-usage.md](references/cli-usage.md).

---

### Operation: Manage ACL

#### Execution — CLI

```bash
# Create ACL
aliyun alb CreateAcl --AclName "{{user.acl_name}}" --RegionId "{{user.region}}"

# Add IP entries to ACL
aliyun alb AddEntriesToAcl \
  --AclId "{{user.acl_id}}" \
  --AclEntries "[{\\"Entry\\":\\"{{user.cidr_block}}\\",\\"EntryDescription\\":\\"{{user.entry_desc}}\\"}]"

# Associate ACL with listener
aliyun alb AssociateAclsWithListener \
  --ListenerId "{{user.listener_id}}" \
  --AclIds "[\\"{{user.acl_id}}\\"]" \
  --AclType "Black"
```

> Full operations (dissociate, delete ACL) at [references/cli-usage.md](references/cli-usage.md).

---

### Operation: Delete ALB Instance

#### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation with `{{user.lb_id}}` and `{{user.lb_name}}`.
- **MUST** verify deletion protection is disabled (`DeletionProtectionEnabled == false`). If enabled, HALT and instruct user to disable first.
- **MUST** warn user that all listeners, rules, and server groups will be cascaded.

#### Execution — CLI

```bash
aliyun alb DeleteLoadBalancer \
  --LoadBalancerId "{{user.lb_id}}" \
  --RegionId "{{user.region}}"
```

#### Post-execution Validation

Poll `ListLoadBalancers` until the instance ID is absent. Max wait: 300s.

---

### Operation: Manage Health Check Template

#### Execution — CLI

```bash
# Create health check template
aliyun alb CreateHealthCheckTemplate \
  --HealthCheckTemplateName "{{user.hc_template_name}}" \
  --HealthCheckProtocol HTTP \
  --HealthCheckPath "{{user.hc_path|/}}" \
  --HealthCheckIntervalSeconds "{{user.hc_interval|2}}" \
  --HealthCheckTimeoutSeconds "{{user.hc_timeout|5}}" \
  --HealthyThreshold "{{user.hc_healthy_threshold|3}}" \
  --UnhealthyThreshold "{{user.hc_unhealthy_threshold|3}}" \
  --HealthCheckHttpCode "{{user.hc_http_code|http_2xx}}"

# Apply to server group
aliyun alb ApplyHealthCheckTemplateToServerGroup \
  --ServerGroupId "{{user.server_group_id}}" \
  --HealthCheckTemplateId "{{user.health_check_template_id}}"
```

---

### Operation: Manage Security Policy

#### Execution — CLI

```bash
# List system security policies
aliyun alb ListSystemSecurityPolicies

# Create custom security policy
aliyun alb CreateSecurityPolicy \
  --SecurityPolicyName "{{user.sp_name}}" \
  --TLSVersion "TLSv1.2" \
  --Ciphers "[\\"ECDHE-RSA-AES128-GCM-SHA256\\",\\"ECDHE-RSA-AES256-GCM-SHA384\\"]"
```

> Associate with HTTPS listener at [references/cli-usage.md](references/cli-usage.md).

---

### Operation: Manage AScript Rules

#### Execution — CLI

```bash
# Create AScript rule
aliyun alb CreateAScripts \
  --ListenerId "{{user.listener_id}}" \
  --AScripts "[{\\"AScriptName\\":\\"{{user.ascript_name}}\\",\\"ScriptContent\\":\\"{{user.script_content}}\\",\\"Enabled\\":true}]"
```

---

### Operation: Manage Tags

#### Execution — CLI

```bash
# Tag resources
aliyun alb TagResources \
  --ResourceType "loadbalancer" \
  --ResourceIds "[\\"{{user.lb_id}}\\"]" \
  --Tag "[{\\"Key\\":\\"{{user.tag_key}}\\",\\"Value\\":\\"{{user.tag_value}}\\"}]"

# Remove tags
aliyun alb UnTagResources \
  --ResourceType "loadbalancer" \
  --ResourceIds "[\\"{{user.lb_id}}\\"]" \
  --Tag "[{\\"Key\\":\\"{{user.tag_key}}\\"}]"
```

---

### Operation: Manage Access Logs

#### Execution — CLI

```bash
# Enable access log (requires SLS project and logstore)
aliyun alb EnableLoadBalancerAccessLog \
  --LoadBalancerId "{{user.lb_id}}" \
  --LogProject "{{user.log_project}}" \
  --LogStore "{{user.log_store}}"

# Disable access log
aliyun alb DisableLoadBalancerAccessLog --LoadBalancerId "{{user.lb_id}}"
```

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting](references/troubleshooting.md)
- [Monitoring & Alerts](references/monitoring.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)

## Operational Best Practices

- **Least privilege:** RAM policies scoped to `alb:*` for required APIs only.
- **Availability:** Multi-zone deployment (≥ 2 zones).
- **Cost:** Match edition to workload (Basic < Standard < StandardWithWaf).
- **Security:** Enable deletion protection on production ALBs; use HTTPS + security policies + ACLs.
- **Tagging:** Tag `Environment`, `Project`, `Owner` for cost allocation.
- **Backup:** Export forwarding rules as JSON before modification.

---

## Quality Gate (GCL)

First rollout of GCL per [`AGENTS.md` §12](../../AGENTS.md#12-generator-critic-loop-gcl--adversarial-quality-gate). See [`references/rubric.md`](references/rubric.md) and [`references/prompt-templates.md`](references/prompt-templates.md).

| Aspect | Setting |
|---|---|
| Required? | **Yes** (Phase 1, ALB skill) |
| `max_iter` | 2 |
| Most-scrutinized | DeleteLoadBalancer, DeleteListener, DeleteServerGroup, RemoveServersFromServerGroup, DeleteAcl, DeleteRule |
| Hard rule | `DeleteLoadBalancer` requires verification of non-serving-production AND disabled deletion protection before execution |

### Changelog
1.0.0 | 2026-06-07 | First rollout.