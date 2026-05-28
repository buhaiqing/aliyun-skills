<!-- markdownlint-disable MD003 MD013 MD022 MD024 MD034 MD041 MD060 -->

# API & SDK — Alibaba Cloud Security Center (Sas)

## OpenAPI

| Property | Value |
|----------|-------|
| **Product** | Sas |
| **Version** | 2018-12-03 |
| **Style** | RPC |
| **Endpoint** | `tds.{regionId}.aliyuncs.com` |
| **Docs** | <https://help.aliyun.com/zh/security-center/developer-reference/api-sas-2018-12-03-overview> |
| **API Explorer** | <https://api.aliyun.com/api/Sas/2018-12-03> |
| **RAM prefix** | `yundun-sas:` |

## SDK Package (JIT Go)

```bash
go get github.com/alibabacloud-go/sas-20181203/v4/client
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
```

## SDK Operations Map

### Asset Management

| Goal | OperationId | SDK Method | CLI Command |
|------|---------------|------------|-------------|
| List assets | DescribeCloudCenterInstances | `DescribeCloudCenterInstances` | `aliyun sas DescribeCloudCenterInstances` |
| Search filters | DescribeCriteria | `DescribeCriteria` | `aliyun sas DescribeCriteria` |
| Asset detail | DescribeAssetDetailByUuids | `DescribeAssetDetailByUuids` | `aliyun sas DescribeAssetDetailByUuids` |
| Asset summary | DescribeAssetSummary | `DescribeAssetSummary` | `aliyun sas DescribeAssetSummary` |
| Global stats | DescribeAllRegionsStatistics | `DescribeAllRegionsStatistics` | `aliyun sas DescribeAllRegionsStatistics` |

### Agent Lifecycle

| Goal | OperationId | SDK Method | CLI Command |
|------|---------------|------------|-------------|
| Create install cmd | AddInstallCode | `AddInstallCode` | `aliyun sas AddInstallCode` |
| List install cmds | DescribeInstallCodes | `DescribeInstallCodes` | `aliyun sas DescribeInstallCodes` |
| Install verify code | DescribeInstallCode | `DescribeInstallCode` | `aliyun sas DescribeInstallCode` |
| Install status | DescribeAgentInstallStatus | `DescribeAgentInstallStatus` | `aliyun sas DescribeAgentInstallStatus` |
| Uninstall | AddUninstallClientsByUuids | `AddUninstallClientsByUuids` | `aliyun sas AddUninstallClientsByUuids` |

### Security Alerts

| Goal | OperationId | SDK Method | CLI Command |
|------|---------------|------------|-------------|
| List alerts | DescribeSuspEvents | `DescribeSuspEvents` | `aliyun sas DescribeSuspEvents` |
| Alert detail | DescribeSuspEventDetail | `DescribeSuspEventDetail` | `aliyun sas DescribeSuspEventDetail` |
| Handle alerts | OperationSuspEvents | `OperationSuspEvents` | `aliyun sas OperationSuspEvents` |
| Export alerts | ExportSuspEvents | `ExportSuspEvents` | `aliyun sas ExportSuspEvents` |
| Quarantine files | DescribeSuspEventQuaraFiles | `DescribeSuspEventQuaraFiles` | `aliyun sas DescribeSuspEventQuaraFiles` |
| Restore file | RollbackSuspEventQuaraFile | `RollbackSuspEventQuaraFile` | `aliyun sas RollbackSuspEventQuaraFile` |

### Vulnerabilities

| Goal | OperationId | SDK Method | CLI Command |
|------|---------------|------------|-------------|
| List vulns | DescribeVulList | `DescribeVulList` | `aliyun sas DescribeVulList` |
| Vuln detail | DescribeVulDetails | `DescribeVulDetails` | `aliyun sas DescribeVulDetails` |
| Fixable list | DescribeCanFixVulList | `DescribeCanFixVulList` | `aliyun sas DescribeCanFixVulList` |
| Vuln statistics | DescribeVulNumStatistics | `DescribeVulNumStatistics` | `aliyun sas DescribeVulNumStatistics` |
| Vuln config | DescribeVulConfig | `DescribeVulConfig` | `aliyun sas DescribeVulConfig` |

### Baseline / Configuration Assessment

| Goal | OperationId | SDK Method | CLI Command |
|------|---------------|------------|-------------|
| Summary | DescribeCheckWarningSummary | `DescribeCheckWarningSummary` | `aliyun sas DescribeCheckWarningSummary` |
| Warnings | DescribeCheckWarnings | `DescribeCheckWarnings` | `aliyun sas DescribeCheckWarnings` |
| Warning detail | DescribeCheckWarningDetail | `DescribeCheckWarningDetail` | `aliyun sas DescribeCheckWarningDetail` |
| Submit scan | SubmitCheck | `SubmitCheck` | `aliyun sas SubmitCheck` |
| Change config | ChangeCheckConfig | `ChangeCheckConfig` | `aliyun sas ChangeCheckConfig` |

### Security Score & AK Leak

| Goal | OperationId | SDK Method | CLI Command |
|------|---------------|------------|-------------|
| Score rules | GetSecurityScoreRule | `GetSecurityScoreRule` | `aliyun sas GetSecurityScoreRule` |
| Change rules | ChangeSecurityScoreRule | `ChangeSecurityScoreRule` | `aliyun sas ChangeSecurityScoreRule` |
| Suggestions | DescribeSecureSuggestion | `DescribeSecureSuggestion` | `aliyun sas DescribeSecureSuggestion` |
| AK leak list | DescribeAccesskeyLeakList | `DescribeAccesskeyLeakList` | `aliyun sas DescribeAccesskeyLeakList` |
| AK leak detail | DescribeAccessKeyLeakDetail | `DescribeAccessKeyLeakDetail` | `aliyun sas DescribeAccessKeyLeakDetail` |
| Handle leak | ModifyAccessKeyLeakDeal | `ModifyAccessKeyLeakDeal` | `aliyun sas ModifyAccessKeyLeakDeal` |

### Scan Tasks

| Goal | OperationId | SDK Method | CLI Command |
|------|---------------|------------|-------------|
| Virus scan once | CreateVirusScanOnceTask | `CreateVirusScanOnceTask` | `aliyun sas CreateVirusScanOnceTask` |
| Cycle task | CreateCycleTask | `CreateCycleTask` | `aliyun sas CreateCycleTask` |
| Cancel task | CancelOnceTask | `CancelOnceTask` | `aliyun sas CancelOnceTask` |

## Key Request Parameters

### DescribeCloudCenterInstances

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| Criteria | string (JSON) | No | Filter array, e.g. `[{"name":"riskStatus","value":"YES"}]` |
| MachineTypes | string | No | `ecs`, `cloud_product`, `eci`, etc. |
| LogicalExp | string | No | `OR` (default) or `AND` |
| PageSize | integer | No | Default 20 |
| CurrentPage | integer | No | Default 1 |
| UseNextToken | boolean | No | `true` for token pagination |
| NextToken | string | No | Continuation token |
| Importance | integer | No | 0 test / 1 general / 2 important |
| Lang | string | No | `zh` or `en` |

### DescribeSuspEvents

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| From | string | No | Start time (epoch ms) |
| To | string | No | End time (epoch ms) |
| PageSize | integer | No | Page size |
| CurrentPage | integer | No | Page number |
| Uuid | string | No | Filter by asset UUID |

### DescribeVulList

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| Type | string | Yes | `cve`, `sys`, `cms`, `app`, etc. |
| PageSize | integer | No | Page size |
| CurrentPage | integer | No | Page number |

## Response Notes

- **Success flag:** Many responses include top-level `Success` (boolean) and `RequestId`
- **Asset list:** `Instances` array; each item includes `Uuid`, `InstanceId`, `ClientStatus`, `RiskStatus`
- **Alerts:** `SuspEvents` array with `SuspUuid`, `Level`, `EventName`, timestamps
- **Pagination:** `TotalCount`, `CurrentPage`, `PageSize`; or `NextToken` when enabled

## Client Initialization (Go)

```go
config := &openapi.Config{
    AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
    AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
    RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
    Endpoint:        tea.String("tds.cn-shanghai.aliyuncs.com"),
}
client, err := sas.NewClient(config)
```

Adjust `Endpoint` to `tds.{region}.aliyuncs.com` per [integration.md](integration.md).

## CLI vs SDK Coverage Gap

| Area | CLI | Notes |
|------|-----|-------|
| Core inventory & alerts | Yes | Full parity for listed operations |
| Playbook / SOAR automation | Partial | Some flows under `sophonsoar` product |
| Console-only wizards | No | Use API equivalents |

Run `aliyun help sas` for the authoritative operation list (500+ APIs). This skill documents **operational core** paths; extend references when adding new flows.
