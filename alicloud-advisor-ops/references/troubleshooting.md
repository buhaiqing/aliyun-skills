# Advisor — Troubleshooting

> **Format:** Each error pattern: code, signature, cause, action.
> See `../../AGENTS.md` and `../SKILL.md` §Failure Recovery for the
> full taxonomy table.

## 1. `UnknownProduct` — CLI does not recognize `advisor`

**Symptom:**
```
$ aliyun advisor DescribeAdvices
ERROR: UnknownProduct: advisor
```

**Cause:** The `aliyun-cli-advisor` plugin is not installed.

**Action:**
```bash
aliyun plugin install --names aliyun-cli-advisor
aliyun advisor version    # verify
```

**Halt vs retry:** HALT (configuration problem).

---

## 2. `PluginNotInstalled` / `PluginVersionMismatch`

**Symptom:** Plugin loads but reports version mismatch.

**Cause:** Plugin version doesn't match the CLI version.

**Action:**
```bash
# Update plugin to latest
aliyun plugin install --names aliyun-cli-advisor

# Or update CLI itself
aliyun --version
# If < 3.3.0, update CLI
```

**Halt vs retry:** HALT.

---

## 3. `Forbidden.RAM` — Insufficient RAM permission

**Symptom:**
```
ERROR: User not authorized to perform operation: advisor:DescribeAdvices
```

**Cause:** The RAM user/role lacks the required `advisor:*` permission.

**Action:**
1. Check current user's policies: `aliyun ram ListPoliciesForUser --UserName <name>`
2. Attach the `AdvisorReadOnly` system policy (read) or
   `AdvisorFullAccess` (read + refresh).
3. For custom policies, see `../SKILL.md` §RAM Permission Reference.

**Halt vs retry:** HALT (requires RAM policy change).

---

## 4. `Throttling.User` / `Throttling.Api` — Rate limit exceeded

**Symptom:**
```
ERROR: Throttling.User: Request was denied due to user flow control
```

**Cause:** Too many calls in a short window. Default limits are
generous for human use but tight for batch jobs.

**Action:**
1. Add delay between calls (1-2 seconds).
2. For batch jobs, implement a sliding-window rate limiter.
3. For long-running batch operations, contact Alibaba Cloud support
   to raise the quota.

**Retry pattern (CLI):**
```bash
for attempt in 1 2 3; do
  if aliyun advisor DescribeAdvices; then break; fi
  sleep $((2 ** attempt))   # 2s, 4s, 8s
done
```

**Halt vs retry:** RETRY (3 attempts, exponential backoff).

---

## 5. `InvalidParameter.CheckId`

**Symptom:** `CheckId` doesn't exist or is misspelled.

**Action:**
```bash
# List valid check IDs
aliyun advisor DescribeAdvisorChecks --product Ecs \
  | jq -r '.Checks[].CheckId' | sort
```

Then re-issue with a valid ID.

**Halt vs retry:** HALT.

---

## 6. `InvalidParameter.Product` / `InvalidParameter.Severity`

**Symptom:** Product or severity value not in the enum.

**Action:**
```bash
# List valid products
aliyun advisor GetProductList | jq -r '.Products[].Code'

# Valid severities: Critical, Warning, Info
```

**Halt vs retry:** HALT.

---

## 7. `InvalidParameter.DateRange`

**Symptom:** `start-date > end-date` or range > 90 days.

**Action:**
```bash
# Validate before calling
python3 -c "
from datetime import date
start = date.fromisoformat('2026-01-01')
end = date.fromisoformat('2026-06-06')
diff = (end - start).days
print(f'Range: {diff} days (max 90)')
assert diff <= 90, 'too wide'
assert end >= start, 'reversed'
print('OK')
"
```

**Halt vs retry:** HALT.

---

## 8. `QuotaExceeded.Inspection` — Daily inspection quota exhausted

**Symptom:** `RefreshAdvisorCheck` returns quota error.

**Action:**
1. Wait until next day (quotas reset at 00:00 UTC).
2. Or upgrade to a paid plan (higher quota).
3. Or use `RefreshAdvisorResource` for single-resource refresh instead
   of full inspection.

**Halt vs retry:** HALT (do not retry same day).

---

## 9. `TaskNotFound` — Inspection task expired

**Symptom:**
```
ERROR: TaskNotFound: Task 12345 not found
```

**Cause:** Inspection tasks have a short retention (1-2 hours). The
caller's `TaskId` is too old.

**Action:**
1. Re-trigger inspection: `RefreshAdvisorCheck`
2. Poll immediately and continuously (don't store the TaskId for
   long-running batch jobs).
3. Save `GmtCreate` of the task; tasks older than 2 hours are gone.

**Halt vs retry:** HALT (cannot recover the same task).

---

## 10. `InspectFailed` — Inspection engine failed

**Symptom:** `GetInspectProgress` reports `Status: Failed`.

**Cause:** Server-side issue. Possible transient (network blip during
scan) or persistent (resource too large, internal error).

**Action:**
1. Retry once with same scope.
2. If retry also fails, narrow scope (single product or single resource).
3. If narrowed scope also fails, report to Alibaba Cloud support with
   the `RequestId` from the failed task.

**Halt vs retry:** RETRY once; if persists, HALT.

---

## 11. `ServiceUnavailable` / `InternalError`

**Symptom:** HTTP 5xx error.

**Action:** Retry with exponential backoff. If persists for > 5 min,
check [Alibaba Cloud status](https://status.aliyun.com).

**Halt vs retry:** RETRY (3 attempts, 2s/4s/8s backoff).

---

## 12. `RequestError` — Network / connectivity

**Symptom:** CLI cannot reach the Advisor endpoint.

**Action:**
1. Test network: `curl -I https://advisor.aliyuncs.com`
2. Check proxy / firewall / VPN.
3. Verify DNS: `dig advisor.aliyuncs.com`
4. Retry once network is restored.

**Halt vs retry:** RETRY after network fix.

---

## 13. Empty Results

**Symptom:** `DescribeAdvices` returns `$.Advices: []` (no errors, just empty).

**Interpretation:** The account is **clean** — no current advisories.
This is normal, especially for:

- Newly created accounts (Advisor has nothing to flag yet).
- Accounts that have fixed all prior issues.

**Action:** No action needed. If the user expected to see results,
confirm the inspection has run (`RefreshAdvisorCheck` then poll).

**Halt vs retry:** None — this is the happy path.

---

## 14. Stale Advices (Resource Already Fixed)

**Symptom:** User fixed a resource, but `DescribeAdvices` still shows
the old advice.

**Cause:** Inspection has not re-run since the fix.

**Action:**
```bash
# Trigger a re-scan of that specific resource
aliyun advisor RefreshAdvisorResource \
  --product Ecs \
  --resource-id i-bp1xxxxxxxxxx
# Then wait a minute, re-run DescribeAdvices
```

Alternatively, run a full `RefreshAdvisorCheck` (more expensive but
thorough).

**Halt vs retry:** None — this is expected behavior.

---

## 15. Multi-Account Issues (`AssumeAliyunId`)

**Symptom:** Cross-account calls fail with `Forbidden.RAM` or
`AssumeRoleFailed`.

**Cause:** The RAM role used does not have permission to assume the
target account, or STS token is missing/expired.

**Action:**
1. Verify the STS role chain is valid: `aliyun sts GetCallerIdentity`
2. Check the target account's trust policy allows assumption.
3. Re-issue the STS credentials if they expired (default 1 hour).

**Halt vs retry:** HALT.

---

## 16. Throttling During Bulk Polling

**Symptom:** Polling `GetInspectProgress` rapidly triggers throttling.

**Cause:** Polling interval < 10s.

**Action:** Use a minimum 30s interval; the standard polling pattern
in [`cli-usage.md`](cli-usage.md#getinspectprogress) is safe.

**Halt vs retry:** RETRY with longer interval.

---

## 17. Date/Time Mismatch in `GetHistoryAdvices`

**Symptom:** `InvalidParameter.DateRange` despite seemingly valid
dates.

**Cause:** Date format wrong (e.g. `2026/06/06` instead of
`2026-06-06`).

**Action:** Always use `YYYY-MM-DD` format with leading zeros.

**Halt vs retry:** HALT.

---

## Quick Diagnostic Flowchart

```
[ Call failed ]
      |
      v
[ Is error code in taxonomy? ] -- no -->  Check General Errors (§11, §12)
      | yes
      v
[ Is it business error? ]
  (InvalidParameter, Forbidden, QuotaExceeded, TaskNotFound)
      | yes
      v
[ HALT — user must fix input / configuration / RAM ]
      |
      | no
      v
[ Is it transient? ]
  (Throttling, ServiceUnavailable, InternalError, RequestError)
      | yes
      v
[ RETRY with backoff (3 attempts) ]
      | persistent failure
      v
[ HALT — escalate to support with RequestId ]
```

## Reporting Bugs

When filing an issue, include:

- `RequestId` from the failed call (printed in error).
- CLI version: `aliyun --version`
- Plugin version: `aliyun advisor version`
- Region (if specified).
- Full command (with secrets **redacted**).
- Time of failure.
- Account ID (the numeric UID, not the name).

## Reference

- [Advisor OpenAPI error codes](https://help.aliyun.com/zh/advisor/developer-reference/error-codes)
- [Alibaba Cloud service health](https://status.aliyun.com)
- [RAM policy reference](../SKILL.md#ram-permission-reference) (in SKILL.md)
