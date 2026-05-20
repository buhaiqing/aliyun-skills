# Well-Architected Assessment — Security Center (SAS)

## §2.1 安全 (Security)

### Minimum RAM Permissions

| Workflow | RAM Action (examples) | Resource |
|----------|----------------------|----------|
| Read assets | `yundun-sas:DescribeCloudCenterInstances` | `acs:yundun-sas:*:*:asset/*` |
| Read alerts | `yundun-sas:DescribeSuspEvents` | `*` |
| Handle alerts | `yundun-sas:OperationSuspEvents` | `*` (restrict in production) |
| Read vulns | `yundun-sas:DescribeVulList` | `*` |
| Agent install | `yundun-sas:AddInstallCode` | `*` |
| AK leak read | `yundun-sas:DescribeAccesskeyLeakList` | `*` |

Use **PoLP**: separate read-only auditor role vs SOC operator role.

### Credential Masking

- Never print `ALIBABA_CLOUD_ACCESS_KEY_SECRET` or leaked secret content from APIs
- Mask AccessKey IDs in reports: first 4 chars + `****`
- `GetSecretValue`-like payloads: show once to authorized user only

### Network Isolation

- Production agents should reach `tds.{region}.aliyuncs.com` via controlled egress
- Prefer **VPC endpoint / proxy** for regulated environments (`tds.vpc-proxy.aliyuncs.com`)
- Restrict management APIs to bastion or CI service accounts

### Security Pillar Checklist

- [ ] All production ECS/ACK covered by online agents
- [ ] Critical alerts routed to on-call (SLS/SMS/webhook)
- [ ] AK leak workflow tied to RAM key rotation
- [ ] No standing full-admin AK on hosts

---

## §2.2 稳定 (Stability)

### Failure-Oriented Design

| Risk | Control |
|------|---------|
| Agent mass offline | Monitor offline ratio; auto-remediation playbooks |
| Alert fatigue | Tuning + whitelist with expiry |
| False isolation | Mandatory confirmation on `OperationSuspEvents` |

### Backup & Recovery

| Data | Mechanism | Notes |
|------|-----------|-------|
| Alert history | `ExportSuspEvents` / SLS export | Long-term retention outside 90-day UI |
| Anti-ransomware backups | `DescribeBackupPolicies` | Separate from standard agent backup |
| Config policies | Export + IaC documentation | Recreate strategies via API |

### DR Runbook (Agent / Posture Loss)

**Phase 1 (0–15 min):** `DescribeAllRegionsStatistics` + list offline agents  
**Phase 2 (15–60 min):** Reinstall agents (`AddInstallCode`); verify `online`  
**Phase 3 (1–24 h):** Full vuln + baseline rescan (`SubmitCheck`, virus scan tasks)

### Multi-Region

- Deploy monitoring per region; use `DescribeAllRegionsStatistics` for global view
- Align API `regionId` with asset home region to avoid empty results

---

## §2.3 成本 (Cost)

### Billing Model (Conceptual)

| Edition | Typical use | Cost driver |
|---------|-------------|-------------|
| Free | Basic visibility | Limited features |
| Advanced / Enterprise / Ultimate | Production SOC | Protected asset count, add-ons |

### Waste Detection

| Pattern | Detection | Action |
|---------|-----------|--------|
| Paid seats on decommissioned VMs | Assets with no ECS match | Remove/unbind |
| Duplicate agents | Same hostname multiple UUIDs | Consolidate |
| Unused advanced modules | `DescribeSasModuleTrial` vs usage | Disable trial/modules |

### Right-Sizing

Match edition to environment: dev/test → lower edition; production regulated → Ultimate + required modules only.

---

## §2.4 效率 (Efficiency)

### Batch Operations

| Task | API pattern |
|------|-------------|
| Bulk agent upgrade | `AddPublishBatch` |
| Bulk tag | `AddTagWithUuid` |
| Bulk defense config | `BatchOperateCommonOverallConfig` |
| Bulk alert handle | `OperationSuspEvents` with UUID list |

### Automation / CI

- Nightly: `DescribeVulNumStatistics` + ticket if critical > 0
- Weekly: `DescribeCheckWarningSummary` export
- On deploy: verify new instances appear in `DescribeCloudCenterInstances` within 1h

---

## §2.5 性能 (Performance)

### Key Metrics

| Metric | Source API | Threshold (example) |
|--------|------------|---------------------|
| Critical open alerts | DescribeSuspEvents filter | > 0 on prod → investigate |
| Mean time to agent online | Install flow timing | < 15 min |
| Unfixed critical CVEs | DescribeVulList Type=cve | Org SLA driven |
| Baseline pass rate | DescribeCheckWarningSummary | < 90% → remediate |

### Auto-Scaling Triggers

Security Center does not autoscale compute for users; trigger **operational scale-out** when:

- Alert rate > 3× 7-day baseline → enable extra analyst shift
- Export jobs queue > 24h → increase export parallelism / SLS capacity

---

## Assessment Summary Template

| Pillar | Status | Top Gap | Next Action |
|--------|--------|---------|-------------|
| 安全 | 🟡/🟢/🔴 | | |
| 稳定 | | | |
| 成本 | | | |
| 效率 | | | |
| 性能 | | | |
