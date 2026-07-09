<!-- markdownlint-disable MD003 MD013 MD022 MD024 MD034 MD041 MD060 -->

# Troubleshooting — Alibaba Cloud Security Center (SAS)

## Error Code Reference

| Error Code | Description | Common Causes | Resolution |
|------------|-------------|---------------|------------|
| `InvalidParameter` | Request validation failed | Malformed `Criteria` JSON, wrong type enum | Fix JSON; call `DescribeCriteria` for valid names |
| `InvalidParameterValue` | Value out of allowed set | Wrong `Type` for DescribeVulList | Use documented enum values |
| `Forbidden.NoPermission` | RAM denied | Missing `yundun-sas:*` actions | Add least-privilege RAM policy |
| `Forbidden.RAM` | RAM policy block | Explicit Deny on resource | Review RAM policies |
| `NoPermission` | Caller not authorized | Sub-account without SAS rights | Grant Security Center read/manage actions |
| `Throttling` / `Throttling.User` | Rate limited | Burst API calls | Exponential backoff; batch reads |
| `InternalError` | Server-side error | Transient outage | Retry with RequestId; escalate if persistent |
| `ServiceUnavailable` | Service unavailable | Maintenance / regional issue | Retry; switch endpoint region if applicable |
| `InvalidAccessKeyId` | AK invalid | Wrong or deleted AK | Fix credentials in env/config |
| `SignatureDoesNotMatch` | Signature failed | Wrong SK, clock skew | Verify SK; sync NTP |
| `MissingParameter` | Required param missing | Omitted `--Type`, `--Uuid`, etc. | Add per `aliyun help sas <Op>` |
| `QuotaExceeded` | Quota hit | Edition/instance limits | Upgrade edition or reduce scope |
| `OperationDenied` | Operation not allowed | Free edition, unbound asset | Check `Version` on asset; bind license |
| `EditionNotSupported` | Feature not in edition | Advanced feature on basic plan | Trial `CreateSasTrial` or upgrade |
| `ClientNotOnline` | Agent offline | Agent not installed / network block | Run install flow; check egress |
| `UuidNotFound` | Unknown asset UUID | Stale UUID, wrong account | Refresh `DescribeCloudCenterInstances` |
| `SuspEventNotFound` | Alert ID invalid | Expired event or wrong ID | Widen time range; re-list events |
| `InstallCodeNotFound` | No install code | Code expired or never created | Call `AddInstallCode` again |

## Diagnostic Order

1. **Credentials** — env vars set; `aliyun sas DescribeAllRegionsStatistics` succeeds
2. **Endpoint region** — `tds.{region}.aliyuncs.com` matches `ALIBABA_CLOUD_REGION_ID`
3. **RAM** — `yundun-sas:DescribeCloudCenterInstances` allowed
4. **Asset visibility** — `DescribeCloudCenterInstances` with empty Criteria
5. **Agent state** — `ClientStatus` for target `Uuid`
6. **Edition** — asset `Version` supports requested feature
7. **Time range** — alert queries use correct epoch milliseconds

## Common Issues

### Issue: Empty asset list

**Causes:** Wrong account, Criteria too strict, assets not synced yet.

**Fix:**

```bash
aliyun sas DescribeCloudCenterInstances --PageSize 20 --CurrentPage 1
aliyun sas DescribeCriteria
```

Wait for asset sync or adjust `ChangeAssetRefreshTaskConfig` if sync interval is long.

### Issue: Agent stays offline

**Causes:** Install command not run, security group blocks outbound HTTPS, wrong UUID.

**Fix:**

```bash
aliyun sas AddInstallCode --Uuid <uuid>
# Run returned command on host
aliyun sas DescribeAgentInstallStatus --Uuid <uuid>
```

Delegate to `alicloud-ecs-ops` for instance network / Cloud Assistant if install automation fails.

### Issue: Cannot handle alerts — OperationDenied

**Causes:** Free edition, offline agent, or insufficient RAM action for `OperationSuspEvents`.

**Fix:** Verify edition and agent online; grant handle permissions; confirm operation enum via API help.

### Issue: Vulnerability list empty but console shows vulns

**Causes:** Wrong `--Type`, pagination, or regional endpoint mismatch.

**Fix:**

```bash
aliyun sas DescribeVulList --Type cve --PageSize 100 --CurrentPage 1
aliyun sas DescribeVulNumStatistics
```

### Issue: Throttling during bulk export

**Fix:** Reduce concurrency; use export APIs (`ExportSuspEvents`, `DescribeExportInfo`) instead of tight loops.

## Multi-Round Diagnosis (Incidents)

| Round | Focus | APIs |
|-------|-------|------|
| 1 | Scope | `DescribeAllRegionsStatistics`, `DescribeCloudCenterInstances` |
| 2 | Alerts | `DescribeSuspEvents`, `DescribeSuspEventDetail` |
| 3 | Host | Agent status, `DescribeVulList`, `DescribeCheckWarningSummary` |
| 4 | Account | `DescribeAccesskeyLeakList` |
| 5 | Audit | Delegate `alicloud-actiontrail-ops` LookupEvents for change timeline |

## Escalation Data to Collect

- `RequestId` from failed response
- Asset `Uuid`, `InstanceId`, `ClientStatus`
- Alert `SuspUuid`, time range
- Edition / `Version` on asset
- Region and endpoint used
