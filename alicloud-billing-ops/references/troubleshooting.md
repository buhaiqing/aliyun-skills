# Troubleshooting — BSSOpenApi

## Error Taxonomy

BSSOpenApi returns structured errors with `Code`, `Message`, and optional `RequestId`. Errors follow the pattern:

```json
{
  "Code": "ErrorCode",
  "Message": "Human-readable description",
  "RequestId": "unique-request-id"
}
```

## Common API Error Codes

| Code | HTTP | Meaning | Agent Action |
|------|------|---------|-------------|
| `NotAuthorized` | 403 | RAM user lacks billing permissions | HALT — verify RAM policy includes `bssapi:Query*` or `bssapi:Get*` |
| `InvalidParameter.BillingCycle` | 400 | Wrong BillingCycle format | FIX — use `YYYY-MM` format |
| `MissingParameter.BillingCycle` | 400 | Required BillingCycle not provided | FIX — add `--BillingCycle 2026-05` |
| `InvalidParameter.DateRange` | 400 | Date range exceeds allowed limit | FIX — reduce range to ≤ 1 month |
| `InvalidOwnerId` | 400 | Invalid or unauthorized UID | HALT — check account ID is correct and authorized |
| `InternalError` | 500 | Server-side processing error | RETRY — up to 3 times with exponential backoff (2s, 4s, 8s) |
| `Throttling.User` | 429 | Rate limit exceeded | RETRY — exponential backoff, max 3 attempts, honor Retry-After header |
| `SignatureDoesNotMatch` | 403 | Invalid access key signature | HALT — verify credentials, check system clock sync |
| `InsufficientBalance` | 400 | Account balance insufficient for operations requiring payment | HALT — inform user to recharge |
| `SubscriptionNotFound` | 404 | Specified subscription/reservation not found | HALT — verify ID is correct and belongs to the account |
| `OrderNotFound` | 404 | Order ID not found | HALT — verify OrderId is correct |
| `InvalidParameter.PageSize` | 400 | PageSize exceeds 100 | FIX — reduce to 100 or less |
| `InvalidParameter.PageNum` | 400 | PageNum less than 1 | FIX — use PageNum >= 1 |
| `ExpiredTimeIsTooLong` | 400 | Query time range too large | FIX — narrow time range |

## Diagnostic Order

When a billing API call fails, follow this sequence:

### Step 1: Verify Credentials

```bash
# Check env vars exist (don't echo values)
test -n "$ALIBABA_CLOUD_ACCESS_KEY_ID" && echo "AK set" || echo "AK missing"
test -n "$ALIBABA_CLOUD_ACCESS_KEY_SECRET" && echo "SK set" || echo "SK missing"

# Verify by calling simplest billing API
aliyun bssopenapi QueryAccountBalance 2>&1 | head -5
```

### Step 2: Check Parameter Format

- BillingCycle: must be `YYYY-MM` (e.g., `2026-05`)
- Date ranges: max 1 month for bills, max 6 months for orders
- PageSize: 1-100 (100 for SettleBill, 20-100 for others)

### Step 3: Verify RAM Permissions

```bash
# Common permission test: if QueryAccountBalance works, billing is accessible
aliyun bssopenapi QueryAccountBalance

# If NotAuthorized, check RAM policy includes:
# bssapi:QueryAccountBalance
# bssapi:QueryBill
# bssapi:QueryInstanceBill
```

### Step 4: Check Rate Limits

If receiving Throttling.User errors, implement:
- Exponential backoff: 2s, 4s, 8s
- Max 3 retries
- For batch operations, add 200ms delay between calls

### Step 5: Validate Data Freshness

- Current month bills may be incomplete (preliminary data)
- Final bills are available around day 3-5 of the following month
- RI/SCU data has ~2 hour delay
- Orders default to last 1 hour; extend range explicitly

## Multi-Round Diagnosis

For persistent errors:

| Symptom | Check | Expected | Fix |
|---------|-------|----------|-----|
| All APIs fail | Network connectivity | `curl -I https://business.aliyuncs.com` | Check firewall, VPC egress rules |
| All APIs fail | Credential rotation | Key creation date via RAM console | Rotate expired/disabled keys |
| QueryBill returns empty | BillingCycle | Date is in `YYYY-MM` format | Verify billing period has charges |
| QueryOrders returns empty | Time range | Default is last 1 hour only | Increase CreateTimeStart range |
| RI/Savings data missing | Data freshness | RI has ~2h delay, SP ~30m | Wait and retry |
| QuerySplitItemBill empty | Feature status | Splitting may not be enabled | Enable in Billing Console first |

## Recovery Patterns

### Pattern: Throttling Retry

```bash
max_retries=3
for i in $(seq 1 $max_retries); do
  RESPONSE=$(aliyun bssopenapi QueryBill --BillingCycle "2026-05" --PageNum 1 --PageSize 100 2>&1)
  if echo "$RESPONSE" | grep -q '"Code":"Throttling.User"'; then
    sleep $((2**i))  # exponential: 2, 4, 8 seconds
  else
    break
  fi
done
```

### Pattern: Pagination Error Recovery

```bash
# If PageSize too large, reduce and retry
PAGE_SIZE=100
RESPONSE=$(aliyun bssopenapi QueryBill --BillingCycle "2026-05" --PageNum 1 --PageSize $PAGE_SIZE 2>&1)
if echo "$RESPONSE" | grep -q 'InvalidParameter.PageSize'; then
  PAGE_SIZE=50
  RESPONSE=$(aliyun bssopenapi QueryBill --BillingCycle "2026-05" --PageNum 1 --PageSize $PAGE_SIZE)
fi
```

## UX Error Messages

All user-facing error messages follow the format:

```
[ERROR] {error.code}: {summary}

What happened:
{explanation}

How to fix:
{steps}

Next step:
{actionable instruction}
```

**Example:**

```
[ERROR] NotAuthorized: This account does not have permission to query billing data.

What happened:
The RAM user or role making this request lacks the required billing API permissions
(bssapi:QueryBill). Billing operations require explicit IAM permissions.

How to fix:
1. Log into RAM console and add the following policy to your RAM user/role:
   - Action: bssapi:Query* (for read) or bssapi:* (for full)
   - Resource: *
2. Alternatively, request the account administrator to grant billing permissions.

Next step:
Run "aliyun bssopenapi QueryAccountBalance" to verify billing access works.
```
