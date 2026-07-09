# AIOps for Alibaba Cloud RAM

> **Purpose:** Proactive security posture management, anomaly detection, and
> auto-remediation for RAM identities, credentials, and policies.

---

## 1. Anomaly Detection

### 1.1 Access Key Usage Anomaly

Detect unusual patterns in AccessKey usage:

| Pattern | Detection Logic | Severity | Action |
|---------|----------------|:--------:|--------|
| **Unused AK** | `GetAccessKeyLastUsed` > 90 days | Medium | Disable → notify → delete after grace period |
| **AK usage spike** | Daily call count > 3σ from 30-day baseline | High | Investigate caller; may indicate compromised key |
| **AK used from new region** | Source IP region differs from user's typical region | **Critical** | Disable immediately; notify security team |
| **AK created outside business hours** | `CreateAccessKey` timestamp not in 09:00-18:00 local | Medium | Verify with user; auto-disable if unconfirmed in 1h |
| **Same AK used from multiple IPs** | Concurrent calls from geographically distant IPs | **Critical** | Disable immediately; possible credential sharing or compromise |

**CLI Detection Example:**

```bash
#!/bin/bash
# detect-ak-anomaly.sh — Check AK usage patterns

USERNAME="{{user.user_name}}"
THRESHOLD_DAYS=90

for key in $(aliyun ram ListAccessKeys --UserName "$USERNAME" --output json | jq -r '.AccessKeys.AccessKey[].AccessKeyId'); do
  STATUS=$(aliyun ram ListAccessKeys --UserName "$USERNAME" --output json | jq -r ".AccessKeys.AccessKey[] | select(.AccessKeyId==\"$key\") | .Status")
  LAST_USED=$(aliyun ram GetAccessKeyLastUsed --UserName "$USERNAME" --UserAccessKeyId "$key" --output json 2>/dev/null | jq -r '.AccessKeyLastUsed.LastUsedDate // "Never"')

  if [ "$LAST_USED" = "Never" ]; then
    echo "ANOMALY: $key has never been used — consider disabling"
  elif [ "$(($(date +%s) - $(date -d "$LAST_USED" +%s)))" -gt $((THRESHOLD_DAYS * 86400)) ]; then
    echo "ANOMALY: $key unused for > ${THRESHOLD_DAYS} days (last: $LAST_USED)"
  else
    echo "OK: $key — active (last: $LAST_USED)"
  fi
done
```

### 1.2 Privilege Escalation Detection

Detect policy or role changes that could enable privilege escalation:

| Pattern | Detection | Severity |
|---------|-----------|:--------:|
| **Wildcard action + resource** | Policy with `Action:*` + `Resource:*` | **Critical** |
| **STS AssumeRole without condition** | Trust policy allows any principal | **Critical** |
| **Cross-account role with broad trust** | `Principal.RAM: ["*"]` or `"acs:ram::*"` | **Critical** |
| **Policy version with escalated privileges** | New policy version broader than previous | High |
| **Service role created without boundary** | `CreateServiceLinkedRole` without permissions boundary | Medium |

### 1.3 Credential Hygiene Anomaly

| Pattern | Detection | Severity | Auto-Remediation |
|---------|-----------|:--------:|------------------|
| **User with 3+ active AKs** | `ListAccessKeys` count > 2 | High | Alert; disable oldest inactive |
| **LoginProfile without MFA** | `GetLoginProfile` exists but no MFA device | High | Recommend enabling MFA |
| **Password never expires** | `GetPasswordPolicy.MaxPasswordAge` = 0 | Medium | Suggest `SetPasswordPolicy` |
| **Console user without login for 90d** | `GetLoginProfile` + login event check | Medium | Consider disabling login profile |

---

## 2. Predictive Analysis

### 2.1 AK Expiry / Rotation Prediction

```bash
#!/bin/bash
# predict-ak-rotation-need.sh

echo "=== AK Rotation Need Assessment ==="

for user in $(aliyun ram ListUsers --MaxItems 100 --output json | jq -r '.Users.User[].UserName'); do
  for key in $(aliyun ram ListAccessKeys --UserName "$user" --output json | jq -r '.AccessKeys.AccessKey[].AccessKeyId'); do
    CREATE_DATE=$(aliyun ram ListAccessKeys --UserName "$user" --output json | jq -r ".AccessKeys.AccessKey[] | select(.AccessKeyId==\"$key\") | .CreateDate")
    DAYS_SINCE_CREATION=$((($(date +%s) - $(date -d "$CREATE_DATE" +%s)) / 86400))

    if [ "$DAYS_SINCE_CREATION" -gt 180 ]; then
      echo "⚠️  $user / $key — created ${DAYS_SINCE_CREATION}d ago (recommend rotation)"
    elif [ "$DAYS_SINCE_CREATION" -gt 90 ]; then
      echo "ℹ️  $user / $key — created ${DAYS_SINCE_CREATION}d ago (plan rotation)"
    fi
  done
done
```

### 2.2 Permission Bloat Trend

Track custom policy size and scope over time:

```bash
# Collect policy statement count as bloat metric
aliyun ram ListPolicies --Scope All --output json | \
  jq -r '.Policies.Policy[] | select(.PolicyType=="Custom") | .PolicyName' | \
  while read -r policy; do
    aliyun ram GetPolicy --PolicyName "$policy" --PolicyType Custom --output json | \
      jq '{name: .Policy.PolicyName, statement_count: [.DefaultPolicyVersion.PolicyDocument | fromjson | .Statement[]] | length}'
  done
```

| Metric | Warning | Critical |
|--------|:-------:|:--------:|
| Policy statement count > 20 | ⚠️ | 🔴 |
| Policies attached to single user > 5 | ⚠️ | 🔴 |
| Groups per user > 3 | ⚠️ | — |
| Roles with trust from > 3 accounts | ⚠️ | 🔴 |

---

## 3. Auto-Remediation

### 3.1 Automated AK Lifecycle

```bash
#!/bin/bash
# auto-ak-lifecycle.sh — Automated AK disable for unused keys
# Dry-run: set DRY_RUN=true for no-op mode

DRY_RUN="${DRY_RUN:-false}"
THRESHOLD_DAYS="${THRESHOLD_DAYS:-90}"

for user in $(aliyun ram ListUsers --MaxItems 100 --output json | jq -r '.Users.User[].UserName'); do
  for key in $(aliyun ram ListAccessKeys --UserName "$user" --output json | jq -r '.AccessKeys.AccessKey[].AccessKeyId'); do
    STATUS=$(aliyun ram ListAccessKeys --UserName "$user" --output json | jq -r ".AccessKeys.AccessKey[] | select(.AccessKeyId==\"$key\") | .Status")
    LAST_USED=$(aliyun ram GetAccessKeyLastUsed --UserName "$user" --UserAccessKeyId "$key" --output json 2>/dev/null | jq -r '.AccessKeyLastUsed.LastUsedDate // "Never"')

    if [ "$LAST_USED" = "Never" ] || [ "$(($(date +%s) - $(date -d "$LAST_USED" +%s)))" -gt $((THRESHOLD_DAYS * 86400)) ]; then
      if [ "$STATUS" = "Active" ]; then
        echo "ACTION: $user / $key — disabling (unused > ${THRESHOLD_DAYS}d)"
        if [ "$DRY_RUN" = "false" ]; then
          aliyun ram UpdateAccessKey --UserName "$user" --UserAccessKeyId "$key" --Status Inactive
          echo "  → Disabled. Schedule deletion after 7-day grace period."
        else
          echo "  → [DRY-RUN] Would disable"
        fi
      fi
    fi
  done
done
```

### 3.2 Remediation Playbook

| Trigger | Auto-Remediation | Requires Approval |
|---------|-----------------|:-----------------:|
| New AK created → notify | Send notification via SLS/EventBridge | No |
| AK unused > 90d → disable | `UpdateAccessKey Status=Inactive` | No (safe) |
| AK unused > 97d → delete | `DeleteAccessKey` | **Yes** |
| Over-permissioned policy detected | Flag in audit report | **Yes** |
| MFA not enabled for console user | Notify user + manager | No |
| Password policy weakened | Restore to compliant baseline | **Yes** |
| Role trust policy over-broad | Flag in audit report | **Yes** |

---

## 4. Security Posture Scoring

### 4.1 Composite Score Calculation

| Dimension | Weight | Measurement |
|-----------|:------:|-------------|
| MFA Coverage | 25% | % of users with MFA enabled |
| AK Hygiene | 25% | % of AKs with rotation < 180d AND unused = 0 |
| Policy Safety | 20% | % of custom policies without wildcard action+resource |
| Password Policy | 15% | Compliance with org standard (length, expiry, complexity) |
| Role Trust Safety | 15% | % of roles with scoped trust principals |

```bash
# Calculate composite security score
# Requires data from `GetPasswordPolicy`, `ListUsers`, `ListPolicies`, `ListRoles`
# Returns 0-100 score
```

### 4.2 Score Interpretation

| Score | Status | Meaning |
|:-----:|:------:|---------|
| 90-100 | ✅ Healthy | RAM security posture is strong |
| 70-89 | ⚠️ Warning | Improvement recommended in 1-2 dimensions |
| 50-69 | 🔴 Critical | Immediate remediation required |
| < 50 | 🚨 Emergency | Active security risk — escalate to security team |

---

## 5. Cross-Skill Orchestration

| Scenario | Primary Skill | Supporting Skills |
|----------|--------------|-------------------|
| Compromised AK detected | `alicloud-ram-ops` | `alicloud-actiontrail-ops` (investigate events) |
| Over-permissioned ECS role | `alicloud-ram-ops` | `alicloud-ecs-ops` (verify impact) |
| Security audit report | `alicloud-ram-ops` | `alicloud-cms-ops` (dashboards) |
| Compliance evidence | `alicloud-ram-ops` | `alicloud-actiontrail-ops` (audit trail) |
| Incident response — AK disable | `alicloud-ram-ops` | `alicloud-sls-ops` (log correlation) |

---

## See Also

- [Intelligent Inspection](intelligent-inspection.md) — Full security audit runbook
- [Monitoring RAM](../monitoring.md) — CMS + ActionTrail monitoring
- [Well-Architected Assessment](../well-architected.md) — Security pillar deep-dive
