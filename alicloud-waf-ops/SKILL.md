<!-- markdownlint-disable MD003 MD013 MD022 MD024 MD034 MD041 MD060 -->

---
name: alicloud-waf-ops
description: >-
  Use when the user needs to deploy, configure, troubleshoot, or monitor Alibaba
  Cloud Web Application Firewall (WAF 3.0, Web应用防火墙) — domain protection,
  access control, CC attack defense, Web core protection rules, rate limiting,
  bot management, threat intelligence, and security analytics. User mentions WAF,
  Web应用防火墙, 网站防护, 防火墙, 域名接入, CC防护, 访问控制, Web核心防护,
  流量防护, 机器人防护, 威胁情报, or describes scenarios like website attacks,
  SQL injection, XSS, DDoS, malicious crawlers, or abnormal access patterns —
  even without naming the product directly. Not for DDoS mitigation (use
  alicloud-ddos-ops), RAM permission design, or pure ECS/SLB lifecycle management.
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun waf-openapi`, Go binary with plugin),
  Go 1.21+ runtime (for JIT SDK fallback), valid API credentials, network
  access to Alibaba Cloud endpoints. Plugin required: `aliyun plugin install
  --names aliyun-cli-waf-openapi`.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-06-05"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "WAF OpenAPI 2021-10-01 / https://help.aliyun.com/zh/waf/web-application-firewall-3-0/developer-reference/api-overview"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun help waf-openapi` — Product WAF (Web Application
    Firewall), Version 2021-10-01. Requires plugin installation:
    `aliyun plugin install --names aliyun-cli-waf-openapi`. Core operations
    (DescribeInstanceInfo, DescribeDomainDetail, ModifyDomain, DescribeIpHitItems,
    DescribeAccessControlList) have matching CLI commands with --version 2021-10-01 --force.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

> This skill follows the [Agent Skill OpenSpec](https://agentskills.io/specification).

# Alibaba Cloud Web Application Firewall (WAF) Operations Skill

## Overview

Alibaba Cloud **Web Application Firewall** (WAF 3.0, Web应用防火墙, API product code **waf-openapi**) provides
comprehensive website protection against OWASP Top 10 threats (SQL injection, XSS, command injection),
DDoS attacks, CC attacks, malicious crawlers, and API abuse. This skill is an **operational runbook**
for agents: explicit scope, credential rules, pre-flight checks, **dual-path execution**
(official **`aliyun waf-openapi`** CLI as primary, **JIT Go SDK** as fallback), response validation,
and failure recovery.

**Primary resource model:** **WAF instances** (identified by `InstanceId`) with associated **protected domains**
(identified by `Domain` / `DomainId`) and **security rules** (access control, custom rules, protection rules).

### CLI applicability (repository policy)

- **`cli_applicability: dual-path`:** Official `aliyun` supports the `waf-openapi` product via plugin.
  Document **both** CLI and SDK paths in each execution flow below. See
  [references/cli-usage.md](references/cli-usage.md) for coverage gaps and plugin installation.

> **Important:** WAF 3.0 CLI requires `--version 2021-10-01 --force` options for all operations.

## Five Core Standards (Quality Gates)

| # | Standard | How This Skill Fulfills It |
|---|----------|---------------------------|
| 1 | **Clear Boundaries** | SHOULD/SHOULD NOT with delegation to DDoS, RAM, ECS, SLB |
| 2 | **Structured I/O** | `{{env.*}}`, `{{user.*}}`, `{{output.*}}` with OpenAPI JSON paths |
| 3 | **Explicit Actionable Steps** | Pre-flight → Execute → Validate → Recover per operation |
| 4 | **Complete Failure Strategies** | ≥ 15 error codes in Failure Recovery + troubleshooting.md |
| 5 | **Absolute Single Responsibility** | One product (WAF); no duplicate DDoS/RAM/ECS flows |

See [references/well-architected-assessment.md](references/well-architected-assessment.md) for five-pillar guidance.

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "WAF" OR "Web应用防火墙" OR "网站防护" OR "防火墙" OR "waf-openapi"
- Task involves **WAF instance lifecycle** (describe instance, query edition, upgrade)
- Task involves **domain protection** (add/remove/modify protected domains, SSL certificates)
- Task involves **access control** (IP blacklist/whitelist, custom access rules)
- Task involves **CC protection** (CC defense policies, rate limiting, challenge rules)
- Task involves **Web core protection rules** (SQL injection, XSS, command injection defenses)
- Task involves **bot management** (malicious bot detection, crawler management)
- Task involves **threat intelligence** (IP reputation, threat intelligence feeds)
- Task involves **security analytics** (visit logs, attack statistics, traffic analysis)
- Task keywords: WAF, 防火墙, 域名接入, CC防护, 访问控制, Web核心防护, 流量防护, 机器人防护, 威胁情报, 攻击防护, SQL注入, XSS

### SHOULD NOT Use This Skill When

- Task is **DDoS mitigation only** → delegate to: `alicloud-ddos-ops` (when present)
- Task is **RAM policy design only** → delegate to: `alicloud-ram-ops`
- Task is **ECS create/stop/resize** without WAF context → delegate to: `alicloud-ecs-ops`
- Task is **SLB load balancing rules** → delegate to: `alicloud-slb-ops`
- Task is **API audit / who deleted rule** → delegate to: `alicloud-actiontrail-ops`
- User insists on **console-only** with no API → state limitation

### Delegation Rules

- **DDoS protection:** WAF handles Layer 7 (application) attacks; for Layer 3/4 DDoS, delegate to `alicloud-ddos-ops`.
- **Origin server reachability:** If origin ECS has issues, use `alicloud-ecs-ops` for instance status/security groups.
- **Load balancing integration:** WAF sits in front of SLB/ALB; for SLB configuration, delegate to `alicloud-slb-ops`.
- Multi-product: complete WAF configuration first, then verify origin server health via relevant skills.

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | Runtime AK | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | Runtime SK | NEVER ask user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | Default region | Use cn-hangzhou for WAF (mainland China) |
| `{{user.region_id}}` | Target region | Ask once; reuse |
| `{{user.instance_id}}` | WAF instance ID | Ask once; reuse |
| `{{user.domain}}` | Protected domain name | Ask once; reuse |
| `{{user.domain_id}}` | Domain ID in WAF | Parse from DescribeDomainDetail |
| `{{user.ip}}` | IP address for ACL rules | Ask once; reuse |
| `{{user.rule_name}}` | Custom rule name | Ask once; reuse |
| `{{user.start_time}}` | Query start (epoch seconds) | Ask once; reuse |
| `{{user.end_time}}` | Query end | Ask once; reuse |
| `{{output.instance_id}}` | WAF instance ID | Parse from DescribeInstanceInfo |
| `{{output.domain_id}}` | Domain ID | Parse from DescribeDomainDetail |
| `{{output.request_id}}` | RequestId | Parse from API response |

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI canonical:** WAF OpenAPI `2021-10-01`, RPC style.
- **Endpoint:** `waf-openapi.{region}.aliyuncs.com` (e.g. `waf-openapi.cn-hangzhou.aliyuncs.com`).
- **RAM action prefix:** `waf:*` (e.g. `waf:DescribeInstanceInfo`).
- **Pagination:** `CurrentPage` + `PageSize` or `NextToken`.
- **CLI invocation:** All operations require `--version 2021-10-01 --force` options.

### Response Field Table

| Operation | JSON Path | Type | Description |
|-----------|-----------|------|-------------|
| DescribeInstanceInfo | `$.InstanceInfo.InstanceId` | string | WAF instance ID |
| DescribeInstanceInfo | `$.InstanceInfo.Edition` | string | Instance edition (version_3.0) |
| DescribeInstanceInfo | `$.InstanceInfo.PayType` | string | Payment type |
| DescribeDomainDetail | `$.Domain.DomainId` | string | Domain ID |
| DescribeDomainDetail | `$.Domain.Domain` | string | Domain name |
| DescribeDomainDetail | `$.Domain.Cname` | string | WAF CNAME for DNS |
| DescribeDomainDetail | `$.Domain.ListenPorts` | array | Protected ports |
| DescribeIpHitItems | `$.IpHitItems[].Ip` | string | IP address |
| DescribeIpHitItems | `$.IpHitItems[].HitCount` | integer | Hit count |
| DescribeAccessControlList | `$.AclRules[].RuleId` | string | ACL rule ID |
| DescribeAccessControlList | `$.AclRules[].Status` | string | Rule status |

## Quick Start

## Prerequisites

见 [执行环境配置](../alicloud-skill-generator/references/execution-environment.md)

### 1. Install WAF CLI Plugin

```bash
# Install WAF plugin (required for waf-openapi CLI)
aliyun plugin install --names aliyun-cli-waf-openapi
```

### 2. Verify Setup

```bash
# Query WAF instance info (JSON output by default)
aliyun waf-openapi DescribeInstanceInfo \
  --RegionId cn-hangzhou \
  --version 2021-10-01 \
  --force
```

### Your First Command

```bash
# List all protected domains
aliyun waf-openapi DescribeDomainList \
  --RegionId cn-hangzhou \
  --InstanceId "{{user.instance_id}}" \
  --version 2021-10-01 \
  --force
```

## Capabilities at a Glance

| Operation | Description | Complexity | Risk Level |
|-----------|-------------|------------|------------|
| DescribeInstanceInfo | Query WAF instance details | Low | None |
| DescribeDomainList | List all protected domains | Low | None |
| DescribeDomainDetail | Query domain protection config | Low | None |
| ModifyDomain | Update domain protection settings | Medium | Medium |
| DeleteDomain | Remove domain from protection | Low | **High** |
| DescribeIpHitItems | Query IP hit statistics | Low | None |
| DescribeAccessControlList | List ACL rules | Low | None |
| CreateAccessControl | Create IP blacklist/whitelist rule | Medium | Medium |
| ModifyAccessControl | Update ACL rule | Medium | Medium |
| DeleteAccessControl | Delete ACL rule | Low | **High** |
| DescribeDefenseRules | List defense rules | Low | None |
| CreateDefenseRule | Create CC/Web protection rule | Medium | Medium |
| ModifyDefenseRule | Update defense rule | Medium | Medium |
| DeleteDefenseRule | Delete defense rule | Low | **High** |
| DescribeVisitTopIp | Top visiting IPs | Low | None |
| DescribeVisitTopUrl | Top visiting URLs | Low | None |
| DescribeLogStatus | Query log collection status | Low | None |

## Execution Flows (Agent-Readable)

Every operation: **Pre-flight → Execute (CLI + SDK) → Validate → Recover**.

> **CLI Note:** All `aliyun waf-openapi` commands MUST include `--version 2021-10-01 --force`.

### Operation: Describe WAF Instance (DescribeInstanceInfo)

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| CLI plugin | `aliyun plugin list \| grep waf` | Plugin installed | Install plugin |
| Credentials | Env vars set | Non-empty | HALT |
| Region | Valid WAF region | cn-hangzhou, cn-shanghai, etc. | Check supported regions |

#### CLI Execution

```bash
# Query WAF instance info
aliyun waf-openapi DescribeInstanceInfo \
  --RegionId "{{user.region_id}}" \
  --version 2021-10-01 \
  --force
```

```bash
# Query instance edition details
aliyun waf-openapi DescribeInstanceEdition \
  --RegionId "{{user.region_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --version 2021-10-01 \
  --force
```

#### SDK Execution (JIT Fallback)

**JIT Go SDK fallback:** 参见 [API & SDK Usage](references/api-sdk-usage.md)

#### Validation

- `$.InstanceInfo.InstanceId` is non-empty
- Report: Edition, PayType, ExpireTime

#### Failure Recovery

| Error | Action |
|-------|--------|
| `InstanceNotFound` | HALT; create WAF instance in console first |
| `InvalidParameter` | HALT; check RegionId format |
| `Forbidden.NoPermission` | HALT; add `waf:DescribeInstanceInfo` permission |

---

### Operation: Add Domain Protection (CreateDomain)

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| WAF instance | DescribeInstanceInfo | Instance exists | HALT; create instance first |
| Domain DNS | Not yet pointing to WAF CNAME | Ready for CNAME update | Warn user about DNS propagation |
| Origin server | Accessible from WAF | Origin reachable | Verify security groups |

#### CLI Execution

```bash
# Add domain to WAF protection
aliyun waf-openapi CreateDomain \
  --RegionId "{{user.region_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --Domain "{{user.domain}}" \
  --ListenPorts '[{"Protocol":"https","Port":443}]' \
  --OriginAddress "{{user.origin_address}}" \
  --OriginProtocol "https" \
  --version 2021-10-01 \
  --force
```

#### Validation

- `$.DomainId` is non-empty
- `$.Cname` is returned — instruct user to update DNS CNAME

#### Post-execution Steps

1. Report WAF CNAME to user
2. Instruct: Update DNS A/CNAME record to point to WAF CNAME
3. Verify: `nslookup {{user.domain}}` should resolve to WAF IP

#### Failure Recovery

| Error | Action |
|-------|--------|
| `DomainAlreadyExists` | HALT; domain already protected, use ModifyDomain |
| `OriginAddressUnreachable` | HALT; verify origin server IP/Port accessibility |
| `InvalidPort` | Fix port format; check allowed port ranges |

---

### Operation: Query Protected Domain (DescribeDomainDetail)

#### CLI Execution

```bash
# Query domain protection configuration
aliyun waf-openapi DescribeDomainDetail \
  --RegionId "{{user.region_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --Domain "{{user.domain}}" \
  --version 2021-10-01 \
  --force
```

#### Validation

- Present: `DomainId`, `Cname`, `ListenPorts`, `OriginAddress`
- Verify CNAME is correctly configured if domain already active

---

### Operation: Remove Domain Protection (DeleteDomain)

> **⚠️ DESTRUCTIVE — Requires explicit user confirmation.**

#### Pre-flight (Safety Gate)

- **MUST** confirm: domain `{{user.domain}}` will be removed from WAF protection
- **MUST** warn: Origin server will be directly exposed after removal
- **MUST NOT** proceed without user assent

#### CLI Execution

```bash
# Remove domain from WAF protection
aliyun waf-openapi DeleteDomain \
  --RegionId "{{user.region_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --Domain "{{user.domain}}" \
  --version 2021-10-01 \
  --force
```

#### Validation

- Re-query `DescribeDomainList` — domain should not appear
- Confirm DNS can be switched back to origin

---

### Operation: Create Access Control Rule (CreateAccessControl)

#### Pre-flight

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| ACL exists | DescribeAccessControlList | Check duplicates | Warn user |
| IP valid | Validate IP/CIDR format | Valid format | HALT; fix format |

#### CLI Execution

```bash
# Create IP blacklist rule
aliyun waf-openapi CreateAccessControl \
  --RegionId "{{user.region_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --Domain "{{user.domain}}" \
  --RuleName "{{user.rule_name}}" \
  --Action "forbidden" \
  --Ip "192.168.1.100" \
  --version 2021-10-01 \
  --force
```

```bash
# Create IP whitelist rule (bypass protection)
aliyun waf-openapi CreateAccessControl \
  --RegionId "{{user.region_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --Domain "{{user.domain}}" \
  --RuleName "trusted-partner" \
  --Action "pass" \
  --Ip "10.0.0.0/8" \
  --version 2021-10-01 \
  --force
```

#### Validation

- `$.RuleId` is non-empty
- Re-query `DescribeAccessControlList` to confirm rule created

#### Failure Recovery

| Error | Action |
|-------|--------|
| `InvalidIpFormat` | HALT; verify IP/CIDR notation |
| `RuleQuotaExceeded` | HALT; delete unused rules or upgrade edition |
| `DomainNotConfigured` | HALT; add domain to WAF first |

---

### Operation: Create CC Defense Rule (CreateDefenseRule)

#### CLI Execution

```bash
# Create CC rate-limiting rule
aliyun waf-openapi CreateDefenseRule \
  --RegionId "{{user.region_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --Domain "{{user.domain}}" \
  --RuleName "api-rate-limit" \
  --RuleType "cc" \
  --DefenseType "rateLimit" \
  --RateLimit 100 \
  --RateInterval 60 \
  --Action "captcha" \
  --version 2021-10-01 \
  --force
```

#### Validation

- `$.DefenseRuleId` is non-empty
- Test: Verify rule triggers on threshold breach

---

### Operation: Query Attack Statistics (DescribeVisitTopIp)

#### CLI Execution

```bash
# Query top attacking IPs
aliyun waf-openapi DescribeVisitTopIp \
  --RegionId "{{user.region_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --Domain "{{user.domain}}" \
  --StartTimestamp {{user.start_time}} \
  --EndTimestamp {{user.end_time}} \
  --version 2021-10-01 \
  --force
```

```bash
# Query top visited URLs
aliyun waf-openapi DescribeVisitTopUrl \
  --RegionId "{{user.region_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --Domain "{{user.domain}}" \
  --StartTimestamp {{user.start_time}} \
  --EndTimestamp {{user.end_time}} \
  --version 2021-10-01 \
  --force
```

#### Validation

- Present top IPs with hit counts
- Flag suspicious IPs for ACL rule creation

---

### Operation: Query IP Blacklist Hit Statistics (DescribeIpHitItems)

#### CLI Execution

```bash
# Query IP blacklist/whitelist hit records
aliyun waf-openapi DescribeIpHitItems \
  --RegionId "{{user.region_id}}" \
  --InstanceId "{{user.instance_id}}" \
  --Domain "{{user.domain}}" \
  --StartTimestamp {{user.start_time}} \
  --EndTimestamp {{user.end_time}} \
  --version 2021-10-01 \
  --force
```

#### Validation

- Present: IP, HitCount, Action
- Identify high-hit IPs for review

---

## Failure Recovery Reference

| Error Code | Description | Retryable | Max Retries | Agent Action |
|------------|-------------|-----------|-------------|--------------|
| `InvalidParameter` | Parameter validation failed | No | 0 | Fix per OpenAPI; retry once if typo |
| `InvalidParameterValue` | Value out of range | No | 0 | HALT; check enums |
| `Forbidden.NoPermission` | RAM denied | No | 0 | HALT; delegate `alicloud-ram-ops` |
| `NoPermission` | Insufficient privilege | No | 0 | HALT; scope `waf:*` minimally |
| `Throttling` | Rate limited | Yes | 3 | Exponential backoff 1s, 2s, 4s |
| `InternalError` | Server error | Yes | 2 | Retry; escalate with RequestId |
| `ServiceUnavailable` | Temporary outage | Yes | 3 | Backoff; check status page |
| `InvalidAccessKeyId` | Bad AK | No | 0 | HALT; fix credentials |
| `SignatureDoesNotMatch` | Bad signature | No | 0 | HALT; fix SK / clock skew |
| `MissingParameter` | Required field missing | No | 0 | HALT; add parameter |
| `InstanceNotFound` | WAF instance not found | No | 0 | HALT; create instance first |
| `DomainAlreadyExists` | Domain already protected | No | 0 | Use ModifyDomain instead |
| `DomainNotFound` | Domain not in WAF | No | 0 | Add domain first |
| `OriginAddressUnreachable` | Origin server unreachable | No | 0 | HALT; verify origin IP/port |
| `InvalidIpFormat` | IP/CIDR format error | No | 0 | HALT; fix format |
| `RuleQuotaExceeded` | Rule quota reached | No | 0 | HALT; delete unused rules |
| `DefenseRuleNotFound` | Defense rule not found | No | 0 | Re-list rules |
| `InvalidPort` | Port format error | No | 0 | Check allowed port ranges |

### HALT vs Retry

| Condition | Decision |
|-----------|----------|
| Permission / parameter / quota errors | **HALT** |
| Throttling / 5xx / network | **Retry** with backoff |
| Origin server unreachable | **HALT** → verify origin health |

## Reference Directory

- [Core Concepts](references/core-concepts.md)
- [API & SDK Usage](references/api-sdk-usage.md)
- [CLI Usage](references/cli-usage.md)
- [Troubleshooting](references/troubleshooting.md)
- [Integration](references/integration.md)
- [Well-Architected Assessment](references/well-architected-assessment.md)

## Operational Best Practices

- **Coverage:** Protect all public-facing web applications with WAF.
- **Defense in depth:** Layer WAF rules — CC protection + access control + Web core rules.
- **Least privilege:** Scope RAM to required `waf:*` actions per workflow.
- **Logging:** Enable WAF log collection to SLS for security audit.
- **Regular review:** Audit ACL rules quarterly; remove outdated IP entries.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-06-05 | Initial WAF 3.0 operations skill with dual-path CLI/SDK |

## See Also — Meta-Skill Rules

This skill is subject to cross-cutting rules defined by the
[alicloud-skill-generator](../alicloud-skill-generator/SKILL.md) meta-skill.
