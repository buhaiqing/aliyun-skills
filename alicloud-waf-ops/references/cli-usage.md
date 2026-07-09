# CLI — Alibaba Cloud WAF (`aliyun waf-openapi`)

## Install and Config

### 1. Install WAF CLI Plugin

WAF 3.0 requires a CLI plugin. Install before first use:

```bash
# Install WAF plugin
aliyun plugin install --names aliyun-cli-waf-openapi

# Verify installation
aliyun plugin list | grep waf
```

### 2. Credentials

The `aliyun` CLI reads from env vars or config file:

```bash
# Environment variables (recommended for Agent execution)
export ALIBABA_CLOUD_ACCESS_KEY_ID="your_access_key_id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your_access_key_secret"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
```

```bash
# Or interactive configuration
aliyun configure
```

## Conventions (Agent Execution)

### Critical: WAF 3.0 CLI Options

**ALL WAF 3.0 commands MUST include:**
- `--version 2021-10-01` — API version
- `--force` — Force call to WAF 3.0 API

```bash
# CORRECT: All options present
aliyun waf-openapi DescribeInstanceInfo \
  --RegionId cn-hangzhou \
  --version 2021-10-01 \
  --force

# WRONG: Missing --version and --force (will call WAF 2.0 or fail)
aliyun waf-openapi DescribeInstanceInfo --RegionId cn-hangzhou
```

### Output Format

- Output is **JSON by default** — NO `--output json` needed
- Use `--output cols=...,rows=...` for JMESPath tabular extraction

```bash
# Plain JSON output (default)
aliyun waf-openapi DescribeDomainList \
  --RegionId cn-hangzhou \
  --InstanceId waf_xxx \
  --version 2021-10-01 \
  --force

# JMESPath tabular extraction
aliyun waf-openapi DescribeDomainList \
  --RegionId cn-hangzhou \
  --InstanceId waf_xxx \
  --output cols=Domain,DomainId rows=DomainList[].{Domain,DomainId} \
  --version 2021-10-01 \
  --force
```

### RPC-style API Structure

```bash
# WAF uses RPC-style API
aliyun waf-openapi <OperationName> --RegionId <region> --Param1 value1 --version 2021-10-01 --force
```

## CLI vs API Coverage Gap

| Operation (API / SDK) | Available via `aliyun`? | Notes |
|------------------------|------------------------|-------|
| DescribeInstanceInfo | ✅ Yes | Requires --version --force |
| CreateDomain | ✅ Yes | Full support |
| DescribeDomainList | ✅ Yes | Full support |
| DescribeDomainDetail | ✅ Yes | Full support |
| ModifyDomain | ✅ Yes | Full support |
| DeleteDomain | ✅ Yes | Full support |
| CreateAccessControl | ✅ Yes | Full support |
| DescribeAccessControlList | ✅ Yes | Full support |
| ModifyAccessControl | ✅ Yes | Full support |
| DeleteAccessControl | ✅ Yes | Full support |
| CreateDefenseRule | ✅ Yes | Full support |
| DescribeDefenseRules | ✅ Yes | Full support |
| ModifyDefenseRule | ✅ Yes | Full support |
| DeleteDefenseRule | ✅ Yes | Full support |
| DescribeVisitTopIp | ✅ Yes | Full support |
| DescribeVisitTopUrl | ✅ Yes | Full support |
| DescribeIpHitItems | ✅ Yes | Full support |
| DescribeLogStatus | ✅ Yes | Full support |
| ModifyLogStatus | ✅ Yes | Full support |

> **Coverage:** CLI has good coverage for WAF 3.0 operations. JIT SDK fallback rarely needed.

## Command Map

### Instance Management

| Goal | Command |
|------|---------|
| Query instance | `aliyun waf-openapi DescribeInstanceInfo --RegionId cn-hangzhou --version 2021-10-01 --force` |
| Query edition | `aliyun waf-openapi DescribeInstanceEdition --RegionId cn-hangzhou --InstanceId waf_xxx --version 2021-10-01 --force` |

### Domain Protection

| Goal | Command |
|------|---------|
| Add domain | `aliyun waf-openapi CreateDomain --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --ListenPorts '[{"Protocol":"https","Port":443}]' --OriginAddress 1.2.3.4 --version 2021-10-01 --force` |
| List domains | `aliyun waf-openapi DescribeDomainList --RegionId cn-hangzhou --InstanceId waf_xxx --version 2021-10-01 --force` |
| Query domain | `aliyun waf-openapi DescribeDomainDetail --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --version 2021-10-01 --force` |
| Update domain | `aliyun waf-openapi ModifyDomain --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --version 2021-10-01 --force` |
| Delete domain | `aliyun waf-openapi DeleteDomain --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --version 2021-10-01 --force` |

### Access Control

| Goal | Command |
|------|---------|
| List rules | `aliyun waf-openapi DescribeAccessControlList --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --version 2021-10-01 --force` |
| Create rule | `aliyun waf-openapi CreateAccessControl --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --RuleName "block-bad-ip" --Action forbidden --Ip 192.168.1.100 --version 2021-10-01 --force` |
| Update rule | `aliyun waf-openapi ModifyAccessControl --RegionId cn-hangzhou --InstanceId waf_xxx --RuleId xxx --version 2021-10-01 --force` |
| Delete rule | `aliyun waf-openapi DeleteAccessControl --RegionId cn-hangzhou --InstanceId waf_xxx --RuleId xxx --version 2021-10-01 --force` |

### Defense Rules

| Goal | Command |
|------|---------|
| List rules | `aliyun waf-openapi DescribeDefenseRules --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --version 2021-10-01 --force` |
| Create rule | `aliyun waf-openapi CreateDefenseRule --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --RuleName "rate-limit" --RuleType cc --DefenseType rateLimit --RateLimit 100 --version 2021-10-01 --force` |

### Traffic Analysis

| Goal | Command |
|------|---------|
| Top IPs | `aliyun waf-openapi DescribeVisitTopIp --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --StartTimestamp 1665331200 --EndTimestamp 1665386280 --version 2021-10-01 --force` |
| Top URLs | `aliyun waf-openapi DescribeVisitTopUrl --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --StartTimestamp 1665331200 --EndTimestamp 1665386280 --version 2021-10-01 --force` |
| IP hits | `aliyun waf-openapi DescribeIpHitItems --RegionId cn-hangzhou --InstanceId waf_xxx --Domain example.com --StartTimestamp 1665331200 --EndTimestamp 1665386280 --version 2021-10-01 --force` |

### Logging

| Goal | Command |
|------|---------|
| Query log status | `aliyun waf-openapi DescribeLogStatus --RegionId cn-hangzhou --InstanceId waf_xxx --version 2021-10-01 --force` |
| Enable logging | `aliyun waf-openapi ModifyLogStatus --RegionId cn-hangzhou --InstanceId waf_xxx --LogOn true --version 2021-10-01 --force` |

## Common Flags

| Flag | Description | Required |
|------|-------------|----------|
| `--RegionId` | Region ID | Yes |
| `--InstanceId` | WAF instance ID | Yes (most ops) |
| `--version` | API version (2021-10-01) | **Yes (MANDATORY)** |
| `--force` | Force WAF 3.0 call | **Yes (MANDATORY)** |
| `--Domain` | Protected domain name | Yes (domain ops) |
| `--PageNumber` | Page number for pagination | No |
| `--PageSize` | Page size (max 100) | No |
