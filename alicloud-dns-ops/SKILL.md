---
name: alicloud-dns-ops
description: >-
  Use this skill to manage Alibaba Cloud DNS services including public authoritative
  DNS resolution, PrivateZone internal DNS, Global Traffic Manager (GTM), DNSSEC,
  and DNS security/compliance. Covers domain resolution record CRUD, line-based
  routing, weighted routing, health checks, disaster recovery, DNS query logs,
  and cross-product DNS integration (SLB, CDN, ECS, VPC, WAF). Triggers on:
  "DNS", "域名解析", "云解析", "PrivateZone", "内网解析", "GTM", "DNSSEC",
  "解析记录", "域名管理", "A记录", "CNAME", "MX记录", "TXT记录", "NS记录",
  "线路策略", "权重路由", "健康检查", "故障切换", "解析日志". Do NOT use for
  domain registration (delegate to domain product), CDN acceleration (delegate to
  CDN product), or general VPC networking (delegate to VPC product).
license: MIT
compatibility: >-
  Official Alibaba Cloud CLI (`aliyun`, Go binary, no runtime), Go 1.21+ runtime
  (for JIT SDK fallback), valid API credentials, network access to Alibaba Cloud
  endpoints.
metadata:
  author: alicloud
  version: "1.0.0"
  last_updated: "2026-07-03"
  runtime: Harness AI Agent, Claude Code, Cursor, or compatible Agent runtimes
  go_version_minimum: "1.21"
  go_version_jit: "1.24+"
  api_profile: "Alidns/2015-01-09, Pvtz/2018-10-10"
  cli_applicability: dual-path
  cli_support_evidence: >-
    Confirmed via `aliyun alidns help` and `aliyun pvtz help`. The `alidns`
    product exposes domain management, record operations, line-based routing,
    GTM, DNSSEC, and query logs. The `pvtz` product covers PrivateZone
    management, VPC bindings, forwarding rules, and internal DNS analytics.
  environment:
    - ALIBABA_CLOUD_ACCESS_KEY_ID
    - ALIBABA_CLOUD_ACCESS_KEY_SECRET
    - ALIBABA_CLOUD_REGION_ID
---

# Alibaba Cloud DNS Operations Skill

## Overview

Alibaba Cloud DNS provides authoritative domain name resolution services with
enterprise-grade features including line-based routing, weighted load balancing,
health checks, disaster recovery, DNSSEC security, and comprehensive logging.
This skill is an **operational runbook** for agents: explicit scope, credential
rules, pre-flight checks, **dual-path execution** (official `aliyun` CLI primary,
**JIT Go SDK** fallback), response validation, and failure recovery.

**Execution surface — CLI-primary with JIT Go SDK fallback:**
- **Primary:** `aliyun alidns <Operation>` and `aliyun pvtz <Operation>` — static
  Go binary, covers domain resolution, record management, line routing, GTM,
  DNSSEC, PrivateZone, and DNS analytics.
- **Fallback:** JIT Go SDK (`github.com/alibabacloud-go/alidns-20150109/v4/client`
  and `github.com/alibabacloud-go/pvtz-20181010/v4/client`) for APIs not exposed
  in CLI or when advanced data processing is needed.
- **Console click-paths** are not an agent execution surface in `SKILL.md`.

**Core capabilities managed by this skill:**

### Public Authoritative DNS (Alidns)
- **Domain Management** — Add domains, verify NS records, check domain status
- **Record Management** — CRUD for A/AAAA/CNAME/MX/TXT/NS/SRV/CAA records
- **Line-Based Routing** — ISP lines, geographic regions, custom lines
- **Weighted Routing** — Traffic distribution across multiple records
- **Health Checks** — Active monitoring with automatic failover
- **GTM 3.0** — Global Traffic Manager with address pools and disaster recovery
- **DNSSEC** — Domain Name System Security Extensions
- **Query Analytics** — DNS query logs, statistics, and real-time monitoring
- **Batch Operations** — Bulk record management with result verification

### Private DNS (PrivateZone)
- **PrivateZone Management** — Internal DNS zones for VPC environments
- **Record Management** — Internal DNS records within PrivateZone
- **VPC Binding** — Associate PrivateZones with VPC instances
- **Forwarding Rules** — Cross-VPC and hybrid cloud DNS resolution
- **Custom Lines** — ISP-based routing for internal DNS
- **Security & Compliance** — DNS query logs, access control, audit trails

## Runtime Rules

| Area | Rule | Reference |
| --- | --- | --- |
| CLI path | **MANDATORY**: Always prefer the SkillOpt wrapper `./scripts/dns-skillopt-wrapper.sh` for all DNS CLI operations to enable automated self-repair and dynamic optimization; fallback to native `aliyun alidns` or `aliyun pvtz` only when the wrapper is unavailable or `skillopt-lib.sh` is missing. | [CLI](references/cli-usage.md), [SkillOpt](references/skillopt-integration.md) |
| Credentials | Read `{{env.*}}` only from environment; never ask user to paste or print secrets | [Integration](references/integration.md) |
| GCL | All write operations MUST pass GCL adversarial review before execution | [GCL Rubric](references/rubric.md) |
| DNS Safety | DNS changes can affect global traffic; always validate NS status and domain ownership before modifications | [DNS Safety](references/dns-safety.md) |

## Trigger & Scope (Agent-Readable)

### SHOULD Use This Skill When

- User mentions "DNS", "域名解析", "云解析", "PrivateZone", "内网解析", "GTM",
  "DNSSEC", "解析记录", "域名管理", "A记录", "CNAME", "MX记录", "TXT记录",
  "NS记录", "线路策略", "权重路由", "健康检查", "故障切换", "解析日志"
- Task involves CRUD or lifecycle operations on **Domain Resolution Records**,
  **PrivateZone**, **GTM**, or **DNSSEC**
- Task requires DNS integration with other Alibaba Cloud services (SLB, CDN,
  ECS, VPC, WAF)
- Task involves DNS troubleshooting, validation, or compliance auditing

### SHOULD NOT Use This Skill When

- Task is purely domain registration/management → delegate to: Domain product
- Task is about CDN acceleration/CDN domain configuration → delegate to: CDN product
- Task is about general VPC networking, routing, or connectivity → delegate to:
  `alicloud-vpc-ops`
- Task is about load balancer configuration only (without DNS) → delegate to:
  `alicloud-slb-ops` or `alicloud-alb-ops`
- Task is about certificate management only → delegate to: CAS product
- User insists on **console-only** flows with no API → state limitation; do not
  invent undocumented HTTP steps

## Delegation Rules

| 能力 | 委托目标 | 说明 |
|------|----------|------|
| GCL 质量门禁 | `alicloud-gcl-runner-ops` | 对写操作执行前，委托 GCL 循环进行对抗性评审 |
| SLB/ALB 配置 | `alicloud-slb-ops`, `alicloud-alb-ops` | DNS CNAME 配置后，委托负载均衡 skill 验证后端健康 |
| CDN 域名接入 | CDN product | DNS CNAME 配置后，委托 CDN skill 验证加速生效 |
| VPC/PrivateZone | `alicloud-vpc-ops` | PrivateZone 与 VPC 绑定后，委托 VPC skill 验证网络连通性 |
| 域名归属验证 | Domain product | DNS 操作前，委托 Domain skill 验证域名所有权和 NS 状态 |
| 安全审计 | `alicloud-actiontrail-ops` | DNS 操作后，委托 ActionTrail skill 审计操作记录 |

## Variable Convention (Agent-Readable)

| Placeholder | Meaning | Agent Action |
|-------------|---------|--------------|
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_ID}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_ACCESS_KEY_SECRET}}` | From runtime environment | NEVER ask the user; fail if unset |
| `{{env.ALIBABA_CLOUD_REGION_ID}}` | From runtime environment | Use documented default only if skill explicitly allows |
| `{{user.domain_name}}` | User-supplied domain name | Ask once; reuse |
| `{{user.record_id}}` | User-supplied or output record ID | Ask if not from previous output |
| `{{user.zone_id}}` | User-supplied or output PrivateZone ID | Ask if not from previous output |
| `{{user.record_type}}` | Record type (A/AAAA/CNAME/MX/TXT/NS/SRV/CAA) | Ask once; validate against allowed types |
| `{{user.record_value}}` | Record value (IP address, domain name, etc.) | Ask once; validate format |
| `{{user.line}}` | Routing line (default/ISP/geographic) | Ask once; default to "default" |
| `{{user.ttl}}` | Time-to-live in seconds | Ask once; default to 600 |
| `{{user.weight}}` | Weight for weighted routing | Ask if weighted routing; validate 1-100 |
| `{{user.health_check_url}}` | Health check endpoint URL | Ask if health checks enabled |
| `{{output.domain_id}}` | From last AddDomain response | Parse `DomainId` from response |
| `{{output.record_id}}` | From last AddRecord response | Parse `RecordId` from response |
| `{{output.zone_id}}` | From last CreateZone response | Parse `ZoneId` from response |

> **`{{env.*}}` MUST NOT** be collected from the user. **`{{user.*}}`** MUST be
> collected interactively when missing.

> **凭据安全（强制）：** 参考 [Credential Masking 规则](../alicloud-skill-generator/references/credential-masking.md)

## API and Response Conventions (Agent-Readable)

- **OpenAPI is canonical** for path, query, body fields, enums, and response
  shapes. DNS uses the **Alidns/2015-01-09** API version for public DNS and
  **Pvtz/2018-10-10** for PrivateZone.
- **Errors:** Map SDK/HTTP errors to `code` / `status` / message fields per spec.
  Common DNS errors: `DomainAlreadyExists`, `DomainNotExists`,
  `RecordAlreadyExists`, `RecordNotExists`, `InvalidParameter`,
  `Forbidden.AliasRecord`, `IncorrectDomainStatus`.
- **Timestamps:** ISO 8601 with timezone when the API returns strings.
- **Idempotency:** Record operations use `RR` + `RecordType` + `Line` as
  natural idempotency key. Domain operations use `DomainName`.

### Response Field Table (DNS-Specific)

| Operation | JSON Path (CLI/SDK) | Type | Description |
|-----------|---------------------|------|-------------|
| AddDomain | `$.DomainId` | string | New domain ID |
| DescribeDomains | `$.Domains.Domain[].DomainId` | array | Domain IDs list |
| DescribeDomainRecords | `$.DomainRecords.Record[].RecordId` | array | Record IDs list |
| AddRecord | `$.RecordId` | string | New record ID |
| UpdateDomainRecord | `$.RecordId` | string | Updated record ID |
| DeleteDomainRecord | `$.RecordId` | string | Deleted record ID |
| DescribeDomainRecords | `$.TotalCount` | int | Total matching records |
| DescribeSubDomainRecords | `$.DomainRecords.Record[]` | array | Sub-domain records |

### Expected State Transitions (DNS Record)

| Operation | Initial State | Target State | Poll Interval | Max Wait |
|-----------|---------------|--------------|---------------|----------|
| AddRecord | — | active | 10s | 60s (1min) |
| UpdateDomainRecord | active | active | 10s | 60s (1min) |
| DeleteDomainRecord | active | absent | 10s | 60s (1min) |
| EnableDomainRecord | paused | active | 10s | 60s (1min) |
| DisableDomainRecord | active | paused | 10s | 60s (1min) |

> **Note:** DNS record operations are typically fast, but propagation across
> name servers may take up to TTL seconds. Always validate record status after
> changes and check NS propagation if needed.

## Core Operations

### Domain Management

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| Add Domain | `aliyun alidns AddDomain --DomainName <domain>` | Add a domain to DNS service |
| List Domains | `aliyun alidns DescribeDomains --PageNumber 1 --PageSize 10` | List managed domains |
| Get Domain Info | `aliyun alidns DescribeDomainInfo --DomainName <domain>` | Get domain details |
| Delete Domain | `aliyun alidns DeleteDomain --DomainName <domain>` | Remove domain from DNS |

### Record Management

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| Add Record | `aliyun alidns AddRecord --DomainName <domain> --RR <subdomain> --Type <type> --Value <value>` | Create DNS record |
| List Records | `aliyun alidns DescribeDomainRecords --DomainName <domain>` | List all records for domain |
| Get Record | `aliyun alidns DescribeDomainRecords --DomainName <domain> --RRKeyWord <rr> --TypeKeyWord <type>` | Get specific record |
| Update Record | `aliyun alidns UpdateDomainRecord --RecordId <id> --RR <rr> --Type <type> --Value <value>` | Update existing record |
| Delete Record | `aliyun alidns DeleteDomainRecord --RecordId <id>` | Delete DNS record |
| Enable Record | `aliyun alidns EnableDomainRecord --RecordId <id>` | Enable paused record |
| Disable Record | `aliyun alidns DisableDomainRecord --RecordId <id>` | Pause record |

### Line-Based Routing

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| Add Line Record | `aliyun alidns AddRecord --DomainName <domain> --RR <rr> --Type <type> --Value <value> --Line <line>` | Add record with line routing |
| List Lines | `aliyun alidns DescribeLines --DomainName <domain>` | List available routing lines |
| Update Line | `aliyun alidns UpdateDomainRecord --RecordId <id> --Line <line>` | Update record line |

### Health Checks & GTM

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| Add Health Check | `aliyun alidns AddGtmAddressPool --Name <name> --Type <type>` | Add GTM address pool |
| Configure Health Check | `aliyun alidns UpdateGtmAddressPool --PoolId <id> --HealthCheckConfig <config>` | Configure health checks |
| Get Health Status | `aliyun alidns DescribeGtmInstanceStatus --InstanceId <id>` | Get GTM health status |
| Trigger Failover | `aliyun alidns SwitchGtmFailoverAddressPool --InstanceId <id>` | Manual failover |

### DNSSEC

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| Enable DNSSEC | `aliyun alidns EnableDnssec --DomainName <domain>` | Enable DNSSEC |
| Disable DNSSEC | `aliyun alidns DisableDnssec --DomainName <domain>` | Disable DNSSEC |
| Get DNSSEC Status | `aliyun alidns DescribeDnssecStatus --DomainName <domain>` | Check DNSSEC status |

### PrivateZone

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| Create Zone | `aliyun pvtz CreateZone --ZoneName <zone>` | Create PrivateZone |
| List Zones | `aliyun pvtz DescribeZones --PageNumber 1 --PageSize 10` | List PrivateZones |
| Add Zone Record | `aliyun pvtz AddZoneRecord --ZoneId <id> --Rr <rr> --Type <type> --Value <value>` | Add internal DNS record |
| Bind VPC | `aliyun pvtz BindZoneVpc --ZoneId <id> --Vpcs <vpc_list>` | Bind zone to VPC |
| Add Forward Rule | `aliyun pvtz AddForwardRule --ZoneName <zone> --Vpcs <vpc_list>` | Add forwarding rule |

### Query Analytics & Logs

| Operation | CLI Command | Description |
|-----------|-------------|-------------|
| Get Query Logs | `aliyun alidns DescribeDnsLogs --DomainName <domain>` | Get DNS query logs |
| Get Statistics | `aliyun alidns DescribeDomainStatistics --DomainName <domain>` | Get query statistics |
| Real-time Monitoring | `aliyun alidns DescribeDnsRealTimeQps` | Real-time QPS data |

## Pre-flight Checks (MANDATORY)

Before any DNS operation, validate:

1. **Credentials** — Verify `ALIBABA_CLOUD_ACCESS_KEY_ID` and
   `ALIBABA_CLOUD_ACCESS_KEY_SECRET` are set
2. **Domain Ownership** — Verify domain is added to DNS service
3. **NS Status** — Verify NS records point to Alibaba Cloud name servers
4. **Record Conflict** — Check for conflicting records (CNAME vs A/AAAA)
5. **TTL Window** — Consider TTL propagation time for changes
6. **Permission Check** — Verify RAM user has DNS permissions

## Error Taxonomy & Recovery

### HALT Errors (Do Not Retry)

| Error Code | Description | Recovery |
|------------|-------------|----------|
| `InvalidParameter` | Invalid parameter format | Fix parameter and retry |
| `Forbidden.AliasRecord` | Alias record conflict | Remove conflicting record |
| `DomainNotExists` | Domain not in DNS service | Add domain first |
| `RecordNotExists` | Record ID not found | Verify record exists |
| `UnauthorizedOperation` | Insufficient RAM permissions | Check RAM policy |

### RETRY Errors (Temporary)

| Error Code | Description | Recovery |
|------------|-------------|----------|
| `Throttling` | API rate limit | Exponential backoff (1s, 2s, 4s) |
| `ServiceUnavailable` | Service temporarily unavailable | Retry with backoff |
| `InternalError` | Internal server error | Retry after 30s |

### FALLBACK Errors (Alternative Path)

| Error Code | Description | Recovery |
|------------|-------------|----------|
| `IncorrectDomainStatus` | Domain in invalid state | Use SDK fallback or wait |
| `InvalidRR.Format` | Subdomain format invalid | Validate RR format |
| `InvalidType.Record` | Record type not supported | Check supported types |

## Validation & Verification

After DNS operations, validate:

1. **Record Status** — Verify record is active/paused as expected
2. **DNS Resolution** — Test `dig`/`nslookup` against Alibaba Cloud DNS servers
3. **Propagation** — Check multiple DNS servers for consistency
4. **Health Checks** — Verify health check status if configured
5. **GTM Failover** — Test failover if GTM is configured

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-07-03 | Initial DNS skill with public authoritative DNS, PrivateZone, GTM, DNSSEC, and query analytics |

> **EXECUTION MANDATORY RULE**: 所有 control-plane CLI 执行步骤 **必须** 通过 SkillOpt wrapper `./scripts/dns-skillopt-wrapper.sh` 运行。
> 以下所有代码块中的 `aliyun alidns ...` 或 `aliyun pvtz ...` 命令在执行时应替换为 `./scripts/dns-skillopt-wrapper.sh <subcommand> ...`。
> 仅在 wrapper 脚本不可用或 `skillopt-lib.sh` 缺失时，才退回到原生 `aliyun alidns` 或 `aliyun pvtz` CLI 调用。
> 参考 `## Runtime Rules` 中的 CLI path 规则。