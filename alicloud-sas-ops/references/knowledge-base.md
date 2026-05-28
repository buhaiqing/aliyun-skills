<!-- markdownlint-disable MD003 MD013 MD022 MD024 MD034 MD041 MD060 -->

# Knowledge Base — Security Center Fault Patterns

## Pattern: Mass Agent Offline After Network Change

**Symptoms:** `ClientStatus=offline` spike; no new alerts; scans fail with `ClientNotOnline`.

**Likely causes:** Security group egress removed, NACL change, proxy misconfiguration, wrong VPC endpoint.

**Diagnosis:**

```bash
aliyun sas DescribeCloudCenterInstances \
  --Criteria '[{"name":"clientStatus","value":"offline"}]' --PageSize 100
```

**Remediation:** Restore HTTPS egress to `tds.*.aliyuncs.com`; rerun `AddInstallCode`; verify online within 15 min.

**Delegate:** `alicloud-vpc-ops` / `alicloud-ecs-ops` for network path validation.

---

## Pattern: Critical CVE on Internet-Facing ECS

**Symptoms:** `DescribeVulList --Type cve` shows high severity; asset `InternetIp` set; `RiskStatus=YES`.

**Diagnosis:**

```bash
aliyun sas DescribeVulDetails --Name <vul_name>
aliyun sas DescribeCloudCenterInstances \
  --Criteria '[{"name":"instanceId","value":"<i-xxx>"}]'
```

**Remediation:** Patch or isolate; use `DescribeCanFixVulList` if auto-fix supported; rescan after patch.

---

## Pattern: Suspicious Process Alert Storm

**Symptoms:** Hundreds of `DescribeSuspEvents` with same `EventName` in short window.

**Diagnosis:** `DescribeSuspEventDetail` on sample `SuspUuid`; check if benign scanner or deployment script.

**Remediation:** If false positive → controlled ignore with documentation; if true positive → `OperationSuspEvents` + host forensics.

**Do not:** Blanket-ignore without time bound.

---

## Pattern: AccessKey Leak Detected

**Symptoms:** `DescribeAccesskeyLeakList` non-empty.

**Diagnosis:**

```bash
aliyun sas DescribeAccessKeyLeakDetail --Id <id>
```

**Remediation:**

1. `ModifyAccessKeyLeakDeal` to mark handling state
2. Delegate `alicloud-ram-ops` — disable/rotate AK immediately
3. `alicloud-actiontrail-ops` — trace usage timeline

---

## Pattern: Baseline Pass Rate Drop After Image Rollout

**Symptoms:** `DescribeCheckWarningSummary` pass rate falls > 10%.

**Diagnosis:** `DescribeCheckWarnings` per failing `RiskId`; map to new AMI/packages.

**Remediation:** `SubmitCheck` after fix; whitelist only approved exceptions via `AddCheckResultWhiteList`.

---

## Pattern: Security Score Drop Without New Alerts

**Symptoms:** Score down in console; few new `DescribeSuspEvents`.

**Diagnosis:**

```bash
aliyun sas GetSecurityScoreRule
aliyun sas DescribeSecureSuggestion --Lang zh
```

**Remediation:** Address deduction modules (unfixed vulns, baseline, exposed ports) per suggestions.

---

## Pattern: OperationSuspEvents Blocked Production

**Symptoms:** User reports blocked IP/process after automated handle.

**Remediation:** Review operation type; use `RollbackSuspEventQuaraFile` if file quarantine; document change ticket.

**Prevention:** Mandatory human confirmation before handle APIs in automation.

---

## Cross-Skill Decision Tree

```text
Security symptom reported
    ├─ Need WHO changed cloud API? → actiontrail-ops
    ├─ Need permission / AK fix? → ram-ops
    ├─ Need instance/network fix? → ecs-ops / vpc-ops
    └─ Host threat / vuln / baseline? → sas-ops (this skill)
```
