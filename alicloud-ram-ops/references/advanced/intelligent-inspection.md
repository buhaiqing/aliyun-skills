# Intelligent Inspection — Alibaba Cloud RAM Security Audit

> **Purpose:** Proactive security inspection for RAM identities, credentials,
> policies, and roles. Combines **periodic audit scripts**, **anomaly detection**,
> and **remediation recommendations** into a single runbook.

---

## 1. Inspection Overview

The RAM intelligent inspection covers 5 security dimensions:

| Dimension | Weight | What It Checks |
|-----------|:------:|----------------|
| **Password Policy** | 20% | Min length ≥ 12, requires symbols/numbers/uppercase/lowercase |
| **User MFA Coverage** | 20% | % of users with MFA enabled |
| **Unused AK Ratio** | 20% | % of access keys used in the last 90 days |
| **Over-Permissioned Policies** | 20% | Custom policies with `Action:*` + `Resource:*` |
| **Password Expiry** | 20% | Max password age ≤ 90 days |

### Scoring

| Score | Status | Meaning |
|:-----:|:------:|---------|
| 90-100 | ✅ Healthy | RAM security posture is strong |
| 70-89 | ⚠️ Warning | Improvement recommended in 1-2 dimensions |
| 50-69 | 🔴 Critical | Immediate remediation required |
| < 50 | 🚨 Emergency | Active security risk — escalate |

---

## 2. Full Inspection Script

### Execution — CLI

```bash
#!/bin/bash
# ram-security-inspection.sh
# Usage: ./ram-security-inspection.sh

SCORE=0
echo "=== RAM Security Inspection ==="
echo ""

# 1. Password policy check
echo "[1/5] Password Policy:"
POLICY=$(aliyun ram GetPasswordPolicy --output json 2>/dev/null)
MIN_LEN=$(echo "$POLICY" | jq -r '.PasswordPolicy.MinimumPasswordLength // 0')
HAS_SYMBOLS=$(echo "$POLICY" | jq -r '.PasswordPolicy.RequireSymbols // false')
MAX_AGE=$(echo "$POLICY" | jq -r '.PasswordPolicy.MaxPasswordAge // 0')
echo "  Min Length: $MIN_LEN, Symbols: $HAS_SYMBOLS, Max Age: $MAX_AGE days"
if [ "$MIN_LEN" -ge 12 ] && [ "$HAS_SYMBOLS" = "true" ]; then
  SCORE=$((SCORE + 20))
  echo "  ✅ Password policy: Strong"
else
  echo "  ⚠️  Password policy: Needs improvement"
fi

# 2. User MFA coverage
echo ""
echo "[2/5] User MFA Coverage:"
USERS=$(aliyun ram ListUsers --MaxItems 100 --output json | jq -r '.Users.User[].UserName')
TOTAL_USERS=$(echo "$USERS" | grep -c . || true)
MFA_USERS=0
for user in $USERS; do
  MFA=$(aliyun ram GetUserMFAInfo --UserName "$user" --output json 2>/dev/null | jq -r '.MFADevice.SerialNumber // ""')
  [ -n "$MFA" ] && MFA_USERS=$((MFA_USERS + 1))
done
echo "  Users: $TOTAL_USERS, MFA enabled: $MFA_USERS"
if [ "$TOTAL_USERS" -gt 0 ]; then
  MFA_RATIO=$((MFA_USERS * 100 / TOTAL_USERS))
  [ "$MFA_RATIO" -eq 100 ] && SCORE=$((SCORE + 20))
  [ "$MFA_RATIO" -ge 50 ] && [ "$MFA_RATIO" -lt 100 ] && SCORE=$((SCORE + 12))
fi

# 3. Unused access keys
echo ""
echo "[3/5] Access Key Audit:"
UNUSED_KEYS=0
TOTAL_KEYS=0
for user in $USERS; do
  KEYS=$(aliyun ram ListAccessKeys --UserName "$user" --output json 2>/dev/null | jq -r '.AccessKeys.AccessKey[].AccessKeyId')
  for key in $KEYS; do
    TOTAL_KEYS=$((TOTAL_KEYS + 1))
    LAST_USED=$(aliyun ram GetAccessKeyLastUsed --UserName "$user" --UserAccessKeyId "$key" --output json 2>/dev/null | jq -r '.AccessKeyLastUsed.LastUsedDate // "Never"')
    [ "$LAST_USED" = "Never" ] && UNUSED_KEYS=$((UNUSED_KEYS + 1))
  done
done
echo "  Total keys: $TOTAL_KEYS, Unused: $UNUSED_KEYS"
[ "$UNUSED_KEYS" -eq 0 ] && SCORE=$((SCORE + 20))
[ "$UNUSED_KEYS" -gt 0 ] && [ "$UNUSED_KEYS" -le "$((TOTAL_KEYS / 2))" ] && SCORE=$((SCORE + 12))

# 4. Over-permissioned policies check
echo ""
echo "[4/5] Policy Audit:"
POLICIES=$(aliyun ram ListPolicies --Scope All --MaxItems 100 --output json | jq -r '.Policies.Policy[] | select(.PolicyType=="Custom") | .PolicyName')
OVER_PERM=0
for policy in $POLICIES; do
  DOC=$(aliyun ram GetPolicy --PolicyName "$policy" --PolicyType Custom --output json 2>/dev/null | jq -r '.DefaultPolicyVersion.PolicyDocument // ""')
  if echo "$DOC" | jq -e '.Statement[] | select(.Action=="*" and .Resource=="*")' > /dev/null 2>&1; then
    OVER_PERM=$((OVER_PERM + 1))
  fi
done
echo "  Custom policies with Action:* + Resource:*: $OVER_PERM"
[ "$OVER_PERM" -eq 0 ] && SCORE=$((SCORE + 20))

# 5. Password expiry check
echo ""
echo "[5/5] Password Expiry:"
if [ "$MAX_AGE" -gt 0 ] && [ "$MAX_AGE" -le 90 ]; then
  SCORE=$((SCORE + 20))
  echo "  ✅ Password expires in $MAX_AGE days"
elif [ "$MAX_AGE" -gt 90 ]; then
  SCORE=$((SCORE + 12))
  echo "  ⚠️  Password expiry > 90 days ($MAX_AGE)"
else
  echo "  ⚠️  Password never expires"
fi

echo ""
echo "=== Inspection Score: $SCORE/100 ==="
if [ "$SCORE" -ge 80 ]; then
  echo "Status: HEALTHY"
elif [ "$SCORE" -ge 60 ]; then
  echo "Status: WARNING — Review recommended"
else
  echo "Status: CRITICAL — Immediate action required"
fi
```

---

## 3. Output Format

```json
{
  "inspection_time": "2026-05-14T10:00:00Z",
  "resource_type": "ram",
  "resource_id": "account",
  "overall_score": 75,
  "dimensions": [
    {"name": "密码策略", "score": 100, "status": "healthy"},
    {"name": "用户MFA覆盖率", "score": 60, "status": "warning", "value": "3/5"},
    {"name": "未使用AK比例", "score": 100, "status": "healthy", "value": "0/10"},
    {"name": "过度授权策略", "score": 0, "status": "critical", "value": "2个"},
    {"name": "密码有效期", "score": 100, "status": "healthy", "value": "90天"}
  ],
  "recommendations": [
    "发现2个自定义策略包含Action:*和Resource:*，建议缩小权限范围",
    "MFA覆盖率60%，建议为所有用户启用MFA"
  ]
}
```

---

## 4. Remediation Recommendations

| Finding | Severity | Remediation |
|---------|:--------:|-------------|
| Password policy too weak | High | `aliyun ram SetPasswordPolicy` with MinLength ≥ 12, RequireSymbols = true |
| Users without MFA | High | `CreateVirtualMFADevice` + `BindMFADevice` per user |
| Unused access keys | Medium | `UpdateAccessKey Status=Inactive` → notify → `DeleteAccessKey` after grace period |
| Over-permissioned policies | **Critical** | Create scoped policies; `AttachPolicy` with specific actions and resources |
| Password never expires | Medium | `SetPasswordPolicy MaxPasswordAge=90` |
| Roles with broad trust | **Critical** | `UpdateRole` to scope trust principal |

---

## 5. Scheduled Inspection

### Daily Quick Check

```bash
# Check 3 critical metrics daily
echo "AK unused: $(aliyun ram ... | jq ...)"
echo "MFA coverage: $(aliyun ram ... | jq ...)"
echo "Password policy: $(aliyun ram GetPasswordPolicy | jq ...)"
```

### Weekly Full Audit

Schedule the full inspection script weekly via Cloud Assistant or cron on a
management ECS instance.

### Automated Alerting

Configure CMS event rules for critical findings:

```bash
# Alert when over-permissioned policy detected (manual trigger for now)
# Full automation requires ActionTrail + SLS + alerting pipeline
```

---

## See Also

- [AIOps for RAM](aiops-ram.md) — Anomaly detection, predictive analysis, auto-remediation
- [Monitoring RAM](../monitoring.md) — CMS metrics and ActionTrail events
- [Audit Operations](../operations/audit-operations.md) — Least-privilege audit
- [Prompt Examples](../prompt-examples.md) — Task templates for inspection flows
