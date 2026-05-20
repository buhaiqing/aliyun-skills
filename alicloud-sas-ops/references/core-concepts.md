# Core Concepts — Alibaba Cloud Security Center (云安全中心)

## What is Security Center?

Security Center (云安全中心, API product **Sas**, formerly Threat Detection Service) is
Alibaba Cloud's unified security operations platform. It provides:

- **Asset center** — inventory of servers, containers, and cloud products with risk tags
- **Threat detection** — real-time alerts (suspicious events) from the Security Center agent
- **Vulnerability management** — CVE/system/app/cms vulnerabilities and fix guidance
- **Baseline / CSPM** — configuration assessment and compliance checks
- **Security score** — aggregated posture score with remediation suggestions
- **Extended capabilities** — AK leak detection, anti-ransomware, honeypot, container security, image scan

Most host-level features require the **Security Center agent** (客户端) installed and **online**.

## Key Concepts

### Asset (资产)

A protected resource registered in Security Center, identified by:

| Field | Description |
|-------|-------------|
| **Uuid** | Security Center internal ID (primary handle for agent APIs) |
| **InstanceId** | Cloud instance ID (e.g. ECS `i-xxx`) |
| **InstanceName** | Display name |
| **ClientStatus** | `online` / `offline` / `pause` |
| **RiskStatus** | `YES` / `NO` — aggregate risk flag |
| **VulStatus** | Whether vulnerabilities exist |
| **SafeEventCount** | Number of security alerts on asset |

**MachineTypes** filter: `ecs`, `cloud_product`, `eci`, `rund`, `runc`.

**Flags** (vendor): `0` Alibaba Cloud, `1` non-Alibaba, `2` IDC, etc.

### Security Center Agent (客户端)

- Lightweight agent on hosts for detection, collection, and response
- **Install:** `AddInstallCode` → run command on host → `DescribeAgentInstallStatus` (within ~2 min)
- **Uninstall:** `AddUninstallClientsByUuids` (removes protection — confirm with user)
- **Offline agents** cannot receive scan/fix commands; triage network and install first

### Alert / Suspicious Event (安全告警)

- API namespace often uses **Susp** (suspicious event)
- **DescribeSuspEvents** — list alerts (time range, pagination)
- **DescribeSuspEventDetail** — full context for one `SuspUuid`
- **OperationSuspEvents** — handle (block, ignore, quarantine, etc.) — **requires confirmation**

### Vulnerability (漏洞)

Types commonly used in `DescribeVulList --Type`:

| Type | Meaning |
|------|---------|
| `cve` | CVE vulnerabilities |
| `sys` | System vulnerabilities |
| `cms` | Web/CMS vulnerabilities |
| `app` | Application vulnerabilities |
| `emg` | Emergency / high-priority |

**DescribeCanFixVulList** — vulnerabilities eligible for automated fix (edition-dependent).

### Baseline / Configuration Assessment (基线检查)

- **Strategy** — policy grouping check items
- **DescribeCheckWarningSummary** — pass rate, risk counts
- **DescribeCheckWarnings** — per-item failures on servers
- Whitelist APIs: `AddBaselineCheckWhiteRecord`, `AddCheckResultWhiteList`

### Security Score (安全评分)

- **GetSecurityScoreRule** / **ChangeSecurityScoreRule** — deduction modules
- **DescribeSecureSuggestion** — remediation guidance linked to score items

### Editions (授权版本)

`Version` on assets (examples from API):

| Value | Edition |
|-------|---------|
| 1 | Free |
| 3 | Enterprise |
| 5 | Advanced |
| 6 | Anti-virus |
| 7 | Ultimate |

Features (auto-fix, advanced threat analytics) depend on edition — expect `EditionNotSupported` when out of scope.

## Architecture & Data Flow

```text
Cloud APIs (Sas 2018-12-03)
        │
        ▼
   tds.{region}.aliyuncs.com
        │
        ├── Asset sync (DescribeCloudCenterInstances)
        ├── Policy / score / vuln metadata
        └── Command channel to agents
                │
                ▼
        Security Center Agent (on host/container)
                │
                ├── Alert generation → DescribeSuspEvents
                ├── Vuln / baseline / virus scans
                └── Response actions ← OperationSuspEvents
```

## Regions & Endpoints

Security Center uses the **tds** endpoint family:

| Type | Pattern |
|------|---------|
| Public (China) | `tds.cn-shanghai.aliyuncs.com` (common default) |
| Regional | `tds.{regionId}.aliyuncs.com` |
| VPC | `tds.vpc-proxy.aliyuncs.com` (region-specific variants) |

Set `ALIBABA_CLOUD_REGION_ID` to the region used for API calls. Some statistics APIs are global (`DescribeAllRegionsStatistics`).

## Quotas & Limits (Operational)

- Large asset lists: use **NextToken** (`UseNextToken=true`) instead of deep page numbers
- **DescribeAgentInstallStatus** only valid within **2 minutes** after install initiated
- Alert export / advanced analytics may require paid editions
- Rate limits: apply backoff on `Throttling` (see troubleshooting.md)

## Dependency Graph

```text
RAM credentials (yundun-sas:*)
    └── Security Center API (tds endpoint)
            ├── Asset inventory
            ├── Agent (requires ECS/network reachability)
            ├── Alerts / Vulns / Baseline
            └── Optional: SLS/OSS export (delegate to sls/oss skills)
```

## Single Points of Failure

| SPOF | Impact | Mitigation |
|------|--------|------------|
| Agent offline | No new host telemetry | Install/repair agent; check outbound 443 |
| Wrong region endpoint | API errors / empty data | Align `regionId` with asset region |
| Over-broad alert ignore | Missed incidents | Use time-bound whitelist; document in runbook |
| AK leak unhandled | Account takeover | `DescribeAccesskeyLeakList` + RAM key rotation |

## Related Products

| Product | Relationship |
|---------|--------------|
| ActionTrail | API audit (complement, not duplicate) |
| RAM | Permissions & AK rotation |
| ECS / ACK | Underlying compute assets |
| WAF | Web layer protection (separate API product) |
| KMS | Encryption keys (separate skill) |
