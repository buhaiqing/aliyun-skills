# Monitoring Alibaba Cloud RAM

> RAM is an **identity and access management** service, not a resource-type service
> (no CPU, memory, disk). Monitoring RAM focuses on **security posture, operational
> activity, and compliance drift** rather than resource utilization.

## Key Security Metrics

RAM monitoring relies on **Cloud Monitor (CMS) events**, **ActionTrail audit logs**,
and **periodic security inspections**.

| Category | Metric / Check | Data Source | Frequency | Alert if |
|----------|---------------|-------------|-----------|----------|
| **Access Key** | AK unused for > 90 days | `GetAccessKeyLastUsed` | Daily | Any |
| **Access Key** | Active AK count per user > 2 | `ListAccessKeys` | Daily | > 2 |
| **Console Login** | Console sign-in failures (5min window) | ActionTrail `ConsoleSignin` events | Real-time | > 5 |
| **Console Login** | LoginProfile exists for inactive users | `ListUsers` + `GetLoginProfile` | Weekly | Mismatch |
| **MFA** | MFA coverage rate | `ListUsers` + `GetUserMFAInfo` | Daily | < 100% |
| **MFA** | Virtual MFA device count change | ActionTrail `CreateVirtualMFADevice` | Real-time | Any |
| **Password Policy** | Password policy compliance drift | `GetPasswordPolicy` | Weekly | Deviation |
| **Policy Change** | Custom policy create/update/delete | ActionTrail `CreatePolicy`/`DeletePolicy` | Real-time | Any |
| **Policy Attachment** | Policy attach/detach frequency | ActionTrail `AttachPolicyToUser`/`DetachPolicyFromUser` | Real-time | > 10/hr |
| **Role Change** | Role trust policy modification | ActionTrail `UpdateRole` | Real-time | Any |
| **User Change** | User create/delete frequency | ActionTrail `CreateUser`/`DeleteUser` | Real-time | Unexpected |
| **Privilege Escalation** | Policy with `Action:*` + `Resource:*` | Custom policy audit | Weekly | Any |

## ActionTrail Event Monitoring

The primary real-time monitoring channel for RAM is **ActionTrail** (操作审计).
Configure ActionTrail to capture RAM management events and route them to SLS/Alerting.

### Key RAM Events to Monitor

```bash
# Lookup RAM management events (last 1 hour)
aliyun actiontrail LookupEvents \
  --Request '{"LookupAttributes":[{"LookupAttributeKey":"ServiceName","LookupAttributeValue":"Ram"}]}' \
  --StartTime "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --MaxResults 50
```

| Event Type | Risk | Description |
|------------|:----:|-------------|
| `CreateUser` / `DeleteUser` | Medium | Identity lifecycle changes |
| `CreateAccessKey` / `DeleteAccessKey` | High | Credential changes — verify legitimacy |
| `CreateLoginProfile` / `DeleteLoginProfile` | Medium | Console access changes |
| `AttachPolicyToUser` / `AttachPolicyToRole` | **Critical** | Permission grant — verify necessity |
| `DetachPolicyFromUser` / `DetachPolicyFromRole` | Medium | Permission revocation — verify no breakage |
| `CreatePolicy` / `DeletePolicy` | High | Custom policy changes — verify content |
| `CreateRole` / `DeleteRole` | High | Role lifecycle changes |
| `UpdateRole` | **Critical** | Trust policy changes — verify no privilege escalation |
| `CreateVirtualMFADevice` / `BindMFADevice` | Low | MFA operations (positive security signal) |
| `SetPasswordPolicy` | Medium | Password policy changes — verify compliance |

### CMS Event Alert Example

```bash
# Create CMS event alarm for RAM policy attachment events
aliyun cms PutEventRule \
  --RuleName "ram-policy-attach-alert" \
  --EventPattern '{
    "product": "Ram",
    "nameList": ["AttachPolicyToUser", "AttachPolicyToRole"],
    "statusList": ["*"],
    "levelList": ["CRITICAL"]
  }' \
  --ContactGroups "ops-team"
```

## Periodic Security Inspection

RAM's most effective monitoring is **periodic security inspection** via the
`aliyun ram` API. Run these checks on a schedule:

### Daily Checks

```bash
#!/bin/bash
# ram-daily-monitor.sh — Daily RAM security checks

echo "=== RAM Daily Security Check ==="

# 1. Unused access keys (> 90 days)
echo "[1/3] Unused Access Keys:"
for user in $(aliyun ram ListUsers --MaxItems 100 --output json | jq -r '.Users.User[].UserName'); do
  for key in $(aliyun ram ListAccessKeys --UserName "$user" --output json | jq -r '.AccessKeys.AccessKey[].AccessKeyId'); do
    LAST_USED=$(aliyun ram GetAccessKeyLastUsed --UserName "$user" --UserAccessKeyId "$key" --output json 2>/dev/null | jq -r '.AccessKeyLastUsed.LastUsedDate // "Never"')
    if [ "$LAST_USED" = "Never" ] || [ "$(($(date +%s) - $(date -d "$LAST_USED" +%s)))" -gt $((90 * 86400)) ]; then
      echo "  ⚠️  $user / $key — last used: $LAST_USED"
    fi
  done
done

# 2. Users without MFA
echo "[2/3] Users without MFA:"
for user in $(aliyun ram ListUsers --MaxItems 100 --output json | jq -r '.Users.User[].UserName'); do
  MFA=$(aliyun ram GetUserMFAInfo --UserName "$user" --output json 2>/dev/null | jq -r '.MFADevice.SerialNumber // ""')
  [ -z "$MFA" ] && echo "  ⚠️  $user — MFA not enabled"
done

# 3. Over-permissioned custom policies
echo "[3/3] Over-permissioned Policies:"
for policy in $(aliyun ram ListPolicies --Scope All --MaxItems 100 --output json | jq -r '.Policies.Policy[] | select(.PolicyType=="Custom") | .PolicyName'); do
  DOC=$(aliyun ram GetPolicy --PolicyName "$policy" --PolicyType Custom --output json 2>/dev/null)
  if echo "$DOC" | jq -e '.DefaultPolicyVersion.PolicyDocument | fromjson | .Statement[] | select(.Action=="*" and .Resource=="*")' > /dev/null 2>&1; then
    echo "  ⚠️  $policy — contains Action:* + Resource:*"
  fi
done
```

### Weekly Checks

| Check | Command | Expected |
|-------|---------|----------|
| Password policy compliance | `aliyun ram GetPasswordPolicy` | MinLength ≥ 12, RequireSymbols = true |
| Role trust policy audit | `aliyun ram ListRoles` → `GetRole` per role | No over-permissive trust principals |
| Group membership audit | `aliyun ram ListGroups` → `ListUsersForGroup` | No unexpected members |
| Cross-account access review | `aliyun ram ListRoles` → trust policy check | Only necessary accounts |

## Anomaly Patterns

| Pattern | Possible Cause | Investigation |
|---------|---------------|---------------|
| **Sudden policy attach spike** | Automation script error or compromised credentials | ActionTrail: check source IP, caller identity |
| **New user creation** | Onboarding automation | Verify with HR/IT system |
| **AccessKey creation outside business hours** | Potential backdoor | Cross-reference with change management |
| **Role trust policy modified** | Cross-account access reconfiguration | Verify new trust principal ARN |
| **Password policy weakened** | Compliance bypass attempt | `GetPasswordPolicy` to confirm current state |
| **MFA unbind without disable** | User troubleshooting or security bypass | Contact user to verify intent |

## Alert Storm Handling

Since RAM events are typically low-volume, an "alert storm" (> 10 RAM events
within 5 minutes) is itself an anomaly:

1. **Pause automated responses**: Do not auto-disable AKs or detach policies
2. **Check ActionTrail source**: Identify the caller (RAM user/role) and source IP
3. **Correlate with other services**: Check ECS/RDS event patterns at the same time
4. **Escalate to security team**: Suspect compromised credentials

## See Also

- [Intelligent Inspection](advanced/intelligent-inspection.md) — Full security audit flow
- [ActionTrail Documentation](https://help.aliyun.com/zh/actiontrail/) — Event history
- [Cloud Monitor Documentation](https://help.aliyun.com/zh/cms/) — Alarm configuration
