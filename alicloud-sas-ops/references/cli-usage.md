# CLI Usage — Alibaba Cloud Security Center (`aliyun sas`)

## Overview

Security Center is exposed as CLI product **`sas`** (version `2018-12-03`).

Optional enhanced plugin:

```bash
aliyun plugin install --names aliyun-cli-sas
```

## Command Structure

```bash
aliyun sas <OperationName> --Param1 value1 --Param2 value2
```

- Output is **JSON by default** — do not pass `--output json` for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- All commands are non-interactive by default

## Credentials

The CLI reads:

- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `ALIBABA_CLOUD_REGION_ID`

Or `~/.aliyun/config.json`.

## CLI Operations Map (Core)

### Asset & Inventory

| Operation | CLI Command |
|-----------|-------------|
| List assets | `aliyun sas DescribeCloudCenterInstances --Criteria '<json>' --PageSize 50` |
| Filter metadata | `aliyun sas DescribeCriteria` |
| Global statistics | `aliyun sas DescribeAllRegionsStatistics` |
| Asset summary | `aliyun sas DescribeAssetSummary` |

### Agent

| Operation | CLI Command |
|-----------|-------------|
| Add install code | `aliyun sas AddInstallCode --Uuid <uuid>` |
| Install codes | `aliyun sas DescribeInstallCodes` |
| Install status | `aliyun sas DescribeAgentInstallStatus --Uuid <uuid>` |
| Uninstall | `aliyun sas AddUninstallClientsByUuids --Uuids '["<uuid>"]'` |

### Alerts

| Operation | CLI Command |
|-----------|-------------|
| List alerts | `aliyun sas DescribeSuspEvents --From <ms> --To <ms> --PageSize 50` |
| Alert detail | `aliyun sas DescribeSuspEventDetail --SuspUuid <id>` |
| Handle alerts | `aliyun sas OperationSuspEvents --Operation <op> --SuspUuidList '[...]'` |
| Export | `aliyun sas ExportSuspEvents` |

### Vulnerabilities

| Operation | CLI Command |
|-----------|-------------|
| List | `aliyun sas DescribeVulList --Type cve --PageSize 50` |
| Detail | `aliyun sas DescribeVulDetails --Name <name>` |
| Fixable | `aliyun sas DescribeCanFixVulList --Type cve` |
| Statistics | `aliyun sas DescribeVulNumStatistics` |

### Baseline

| Operation | CLI Command |
|-----------|-------------|
| Summary | `aliyun sas DescribeCheckWarningSummary` |
| Warnings | `aliyun sas DescribeCheckWarnings` |
| Submit scan | `aliyun sas SubmitCheck` |

### Score & AK Leak

| Operation | CLI Command |
|-----------|-------------|
| Score rules | `aliyun sas GetSecurityScoreRule` |
| Suggestions | `aliyun sas DescribeSecureSuggestion --Lang zh` |
| AK leaks | `aliyun sas DescribeAccesskeyLeakList` |

### Scans

| Operation | CLI Command |
|-----------|-------------|
| Virus scan | `aliyun sas CreateVirusScanOnceTask --UuidList '["<uuid>"]'` |

## Common Examples

### List high-risk ECS assets with offline agents

```bash
aliyun sas DescribeCloudCenterInstances \
  --Criteria '[{"name":"riskStatus","value":"YES"},{"name":"clientStatus","value":"offline"}]' \
  --MachineTypes ecs \
  --LogicalExp AND \
  --PageSize 50 \
  --CurrentPage 1
```

### Extract asset fields (JMESPath)

```bash
aliyun sas DescribeCloudCenterInstances \
  --Criteria '[{"name":"riskStatus","value":"YES"}]' \
  --PageSize 20 \
  --output cols=Uuid,InstanceId,ClientStatus,InstanceName rows=Instances[].{Uuid,InstanceId,ClientStatus,InstanceName}
```

### Recent alerts (last 24h — compute epoch ms externally)

```bash
aliyun sas DescribeSuspEvents \
  --From 1716163200000 \
  --To 1716249600000 \
  --PageSize 50 \
  --CurrentPage 1
```

### CVE vulnerabilities page 1

```bash
aliyun sas DescribeVulList --Type cve --PageSize 50 --CurrentPage 1
```

## CLI vs API Coverage Gap

| Operation (API) | CLI | Notes |
|-----------------|-----|-------|
| DescribeCloudCenterInstances | yes | Primary inventory API |
| DescribeSuspEvents | yes | |
| OperationSuspEvents | yes | Confirm `Operation` enum via help |
| DescribeVulList | yes | `--Type` required |
| SubmitCheck | yes | Baseline scan trigger |
| SOAR playbooks | partial | Use `sophonsoar` CLI product when needed |
| Console-only report designer | no | Use `DescribeChartList` / export APIs |

## Verification Commands

```bash
aliyun version
aliyun help sas | head -20
aliyun sas DescribeAllRegionsStatistics
```

## JSON Path Verification

After each new CLI invocation, verify paths with:

```bash
aliyun sas DescribeCloudCenterInstances --PageSize 1 | jq '.Instances[0] | keys'
aliyun sas DescribeSuspEvents --PageSize 1 | jq '.SuspEvents[0] | keys'
```

Document verified paths in SKILL.md — do not invent field names.
