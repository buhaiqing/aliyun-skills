# Well-Architected Assessment — BSSOpenApi (Billing)

> Aligned with Alibaba Cloud Well-Architected Framework (卓越架构) five pillars.
> Reference: https://help.aliyun.com/zh/product/2362200.html

## 1. Security Pillar (安全)

### 1.1 IAM & Access Management

Billing APIs expose highly sensitive financial data. Follow the principle of least privilege.

**Minimum RAM Permissions:**

| API Operation | Required RAM Action | Scope |
|---------------|--------------------|-------|
| QueryAccountBalance | `bssapi:QueryAccountBalance` | `*` |
| QueryBill / QueryBillOverview | `bssapi:QueryBill` | `*` |
| QueryInstanceBill | `bssapi:QueryInstanceBill` | `*` |
| QuerySettleBill | `bssapi:QuerySettleBill` | `*` |
| QueryAccountBill | `bssapi:QueryAccountBill` | `*` |
| QuerySplitItemBill | `bssapi:QuerySplitItemBill` | `*` |
| QueryOrders / GetOrderDetail | `bssapi:QueryOrders`, `bssapi:GetOrderDetail` | `*` |
| QueryRIUtilizationDetail | `bssapi:QueryRIUtilizationDetail` | `*` |
| QuerySavingsPlans* | `bssapi:QuerySavingsPlansInstance`, `bssapi:QuerySavingsPlansDeductLog` | `*` |
| QueryResourcePackageInstances | `bssapi:QueryResourcePackageInstances` | `*` |
| QueryAccountTransactions | `bssapi:QueryAccountTransactions` | `*` |
| QueryPrepaidCards | `bssapi:QueryPrepaidCards` | `*` |
| QueryCashCoupons | `bssapi:QueryCashCoupons` | `*` |

**Best Practices:**
- DO NOT use `AdministratorAccess` for billing queries
- Create dedicated RAM role for billing read operations
- Use STS temporary credentials for cross-account billing access
- Rotate AccessKey pairs every 90 days
- Enable MFA for all billing-accessible RAM users

### 1.2 Credential Security

- **MANDATORY masking:** NEVER log `ALIBABA_CLOUD_ACCESS_KEY_SECRET`, `AccessKeySecret`, or any credential value
- Env variable verification: `test -n "$var" && echo "set"` (NO echo of value)
- JIT Go SDK: `os.Getenv()` reads are safe; `fmt.Printf("%+v", config)` is NOT
- Masking format: `ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>`

### 1.3 Network Security

- All API calls use HTTPS to `business.aliyuncs.com`
- Prefer VPC endpoints for private network access
- For JIT Go SDK: ensure outbound HTTPS (443) connectivity
- API calls are region-independent (default: cn-hangzhou)

### 1.4 Data Classification

Billing data is **highly confidential**. Classification:

| Data Type | Sensitivity | Access Control |
|-----------|------------|----------------|
| Account Balance | P0 - Critical | RAM role with explicit allow |
| Bill Details | P1 - High | Product-scoped read policy |
| Order History | P1 - High | Time-scoped query limits |
| RI/SP Coverage | P2 - Medium | Read-only billing role |
| Resource Package Status | P2 - Medium | Product-scoped read |

---

## 2. Stability Pillar (稳定)

### 2.1 Failure-Oriented Design

BSSOpenApi is read-heavy with no destructive operations. Stability risks:

| Risk | Mitigation |
|------|-----------|
| API endpoint outage | Retry with exponential backoff; business.aliyuncs.com is a single endpoint (no DR) |
| Rate limiting | Implement backoff (2s, 4s, 8s), max 3 retries, respect Retry-After |
| Pagination failures | Fallback to smaller PageSize; detect PageSize errors and auto-adjust |
| Data inconsistency | Validate BillingCycle matches expected; check TotalCount for completeness |

### 2.2 Operational Control

- All operations are read-only (query/describe/get) — no destructive risk
- Data freshness is documented per operation type
- API version is pinned in metadata (`2017-12-14`)

### 2.3 Emergency Recovery

BSSOpenApi has no resource CRUD — recovery focus is on:

**Phase 1: Diagnose**
1. Verify credentials via `QueryAccountBalance` (simplest API)
2. Check network: `curl -I https://business.aliyuncs.com`
3. Confirm RAM policy includes `bssapi:Query*`

**Phase 2: Mitigate**
1. Retry with backoff for InternalError / Throttling
2. Reduce PageSize for pagination errors
3. Narrow time ranges for date range errors

**Phase 3: Escalate**
1. Capture RequestId from error response
2. Document: timestamp, operation, error code, full response
3. Escalate via Alibaba Cloud Support with RequestId

---

## 3. Cost Pillar (成本)

### 3.1 Cost Visibility

BSSOpenApi IS the cost visibility layer. Key capabilities:

| Capability | API | Use Case |
|-----------|-----|----------|
| Real-time balance | QueryAccountBalance | Budget tracking |
| Monthly overview | QueryBillOverview | Executive reporting |
| Product-level break down | QueryBill | Cost attribution |
| Instance-level detail | QueryInstanceBill | Idle resource detection |
| Split billing | QuerySplitItemBill | FinOps showback/chargeback |

### 3.2 Billing Model Comparison

| Billing Type | Best Use Case | API to Monitor |
|-------------|---------------|---------------|
| Pay-As-You-Go (按量付费) | Dev/test, variable workloads | QueryBill with SubscriptionType=PayAsYouGo |
| Subscription (包年包月) | Production, stable workloads | QueryBill with SubscriptionType=Subscription |
| Reserved Instances (RI) | Predictable 24/7 workloads | QueryRIUtilizationDetail |
| Savings Plans (SP) | Committed spend discount | QuerySavingsPlansInstance |
| Resource Packages (资源包) | Pre-paid resource blocks | QueryResourcePackageInstances |

### 3.3 Waste Detection Patterns

| Pattern | Detection Method | Resolution |
|---------|-----------------|------------|
| RI under-utilization | QueryRIUtilizationDetail: RIUtilizationRatio < 50% | Modify RI to match actual usage |
| Uncovered RI-eligible spend | DescribeResourceCoverageTotal: coverage < 70% | Purchase additional RI |
| SP pool depletion | QuerySavingsPlansInstance: CurrentPoolValue < threshold | Top up savings plan |
| Expiring resource packages | QueryResourcePackageInstances: ExpiryTime within 30 days | Renew or replace |
| Idle reserved instances | Cross-reference QueryInstanceBill + CMS CPU metrics | Release or convert to pay-as-you-go |

### 3.4 Right-Sizing Recommendations

| Utilization | Recommendation |
|------------|---------------|
| < 30% sustained | Downgrade instance spec or convert to pay-as-you-go |
| 30-60% | Review RI commitment level |
| 60-80% | Optimal — continue monitoring |
| > 80% sustained | Consider RI purchase or upgrade |

---

## 4. Efficiency Pillar (效率)

### 4.1 Batch Operations

BSSOpenApi supports paginated batch queries:

```bash
# Batch fetch all bills for a month
PAGE=1; PAGE_SIZE=100
while true; do
  RESPONSE=$(aliyun bssopenapi QueryBill \
    --BillingCycle "2026-05" --PageNum $PAGE --PageSize $PAGE_SIZE)
  TOTAL=$(echo "$RESPONSE" | jq -r '.Data.TotalCount')
  echo "$RESPONSE" | jq '.Data.Items.Item[]'
  TOTAL_PAGES=$(( (TOTAL + PAGE_SIZE - 1) / PAGE_SIZE ))
  if [ $PAGE -ge $TOTAL_PAGES ]; then break; fi
  PAGE=$((PAGE + 1))
done
```

### 4.2 Automation Patterns

| Pattern | Implementation | Frequency |
|---------|---------------|-----------|
| Daily cost report | Cron + QueryBillOverview → Slack/Email | Daily |
| Weekly RI coverage check | Cron + DescribeResourceCoverageTotal → report | Weekly |
| Monthly FinOps review | Cron + QueryBill + QuerySplitItemBill → dashboard | Monthly |
| Expiration alerts | Cron + QueryResourcePackageInstances → alert | Daily |

### 4.3 CI/CD Integration

Bills from CI/CD pipeline usage can be tracked:

```bash
# In pipeline: query cost by tag
aliyun bssopenapi QuerySplitItemBill \
  --BillingCycle "$(date +%Y-%m)" \
  --TagKey "Pipeline" \
  --TagValue "production-deploy"
```

---

## 5. Performance Pillar (性能)

### 5.1 API Performance Characteristics

| Operation | Typical Latency | Data Volume | Optimization |
|-----------|----------------|-------------|-------------|
| QueryAccountBalance | < 200ms | 4 fields | No optimization needed |
| QueryBillOverview | < 500ms | < 100 items | Filter by ProductCode |
| QueryBill | < 1s | Up to 100/Page | Use ProductCode filter |
| QueryInstanceBill | < 2s | Up to 100/Page | Filter by BillingType |
| QuerySettleBill | < 3s | Up to 100/Page | Use for large datasets |
| QuerySplitItemBill | < 2s | Up to 100/Page | Filter by Tag |
| QueryOrders | < 1s | Up to 100/Page | Narrow time range |

### 5.2 Performance Optimization

- **Filter early:** Use ProductCode, SubscriptionType, BillingType filters to reduce result size
- **Page efficiently:** Use PageSize=100 for minimal API calls
- **Cache balance:** QueryAccountBalance is real-time; cache with 5-min TTL
- **Batch strategically:** Combine multiple product filters into single QueryBill call
- **Avoid large date ranges:** Bills are monthly; don't query beyond BillingCycle window

### 5.3 Scaling Considerations

- BSSOpenApi scales automatically — no user configuration needed
- Rate limits apply per-account; for high-frequency queries, implement client-side throttling
- For accounts with 10,000+ billing items, QuerySettleBill is recommended over QueryBill

---

## Maturity Assessment

| Pillar | Maturity Level | Notes |
|--------|---------------|-------|
| Security | L2 - Actionable | IAM policies documented; credential masking verified |
| Stability | L1 - Compliant | Error taxonomy with retry/HALT; pagination recovery patterns |
| Cost | L3 - Automated | Cost anomaly detection scripts provided; waste detection patterns documented |
| Efficiency | L2 - Actionable | Batch pagination; CI/CD integration patterns |
| Performance | L1 - Compliant | Latency characteristics and optimization tips documented |
