# Monitoring — BSSOpenApi (Billing)

BSSOpenApi does not expose CloudMonitor metrics directly (it is a financial API, not a resource API). However, monitoring billing-related patterns requires combining billing data with CloudMonitor metrics from other products.

## Key Monitoring Scenarios

### 1. Cost Anomaly Detection

Monitor for unexpected billing spikes using month-over-month comparison:

```bash
# Current month total
CURRENT_TOTAL=$(aliyun bssopenapi QueryBillOverview \
  --BillingCycle "$(date +%Y-%m)" | jq '[.Data.Items.Item[].PretaxAmount | tonumber] | add')

# Last month total
LAST_TOTAL=$(aliyun bssopenapi QueryBillOverview \
  --BillingCycle "$(date -v-1m +%Y-%m)" | jq '[.Data.Items.Item[].PretaxAmount | tonumber] | add')

# Alert if >30% increase
if [ -n "$CURRENT_TOTAL" ] && [ -n "$LAST_TOTAL" ] && [ "$LAST_TOTAL" != "0" ]; then
  INCREASE=$(echo "scale=2; ($CURRENT_TOTAL/$LAST_TOTAL - 1) * 100" | bc)
  if (( $(echo "$INCREASE > 30" | bc -l) )); then
    echo "[ALERT] Cost anomaly: ${INCREASE}% increase from $LAST_TOTAL to $CURRENT_TOTAL"
  fi
fi
```

### 2. Resource Package Expiration Monitoring

Monitor resource packages approaching expiration:

```bash
# Check packages expiring within 30 days
aliyun bssopenapi QueryResourcePackageInstances --PageNum 1 --PageSize 100 | \
  jq -r '.Data.Instances.Instance[] | select(.Status=="Valid") |
    [.InstanceId, .PackageType, .RemainingAmount, .TotalAmount, .ExpiryTime] | @tsv' | \
  while IFS=$'\t' read id type remaining total expiry; do
    EXPIRY_TS=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$expiry" +%s 2>/dev/null || \
                date -d "$expiry" +%s 2>/dev/null)
    NOW_TS=$(date +%s)
    DAYS_LEFT=$(( (EXPIRY_TS - NOW_TS) / 86400 ))
    if [ "$DAYS_LEFT" -le 30 ] && [ "$DAYS_LEFT" -ge 0 ]; then
      echo "[WARN] $type ($id): $remaining/$total remaining, expires in $DAYS_LEFT days ($expiry)"
    fi
  done
```

### 3. RI/SCU Coverage Monitoring

Monitor Reservation Instance and SCU coverage gaps:

```bash
# Check RI coverage
COVERAGE=$(aliyun bssopenapi DescribeResourceCoverageTotal 2>&1)
if echo "$COVERAGE" | jq -e '.Data.TotalCoverage.CoveragePercentage' > /dev/null 2>&1; then
  COV_PCT=$(echo "$COVERAGE" | jq -r '.Data.TotalCoverage.CoveragePercentage')
  if (( $(echo "$COV_PCT < 70" | bc -l) )); then
    echo "[WARN] RI/SCU coverage low: ${COV_PCT}%. Recommend purchasing additional reservations."
  fi
fi
```

### 4. Savings Plans Pool Depletion

Monitor savings plans pool value approaching zero:

```bash
# Check each SP pool value
aliyun bssopenapi QuerySavingsPlansInstance --PageNum 1 --PageSize 100 | \
  jq -r '.Data.Items[] | [.InstanceId, .SavingsType, .CurrentPoolValue, .Status] | @tsv' | \
  while IFS=$'\t' read id type value status; do
    if [ "$status" = "NORMAL" ] && (( $(echo "$value < 100" | bc -l) )); then
      echo "[WARN] SP $id ($type): pool value low (${value}), deduct will stop soon"
    fi
  done
```

## Alert Integration

### CMS Alarm Template

Though BSSOpenApi itself lacks CMS metrics, you can set up custom alarms via Function Compute + CMS:

```yaml
# Conceptual: Schedule FC to run billing check, push metric to CMS
metric_name: "billing.monthly_total"
namespace: "acs_custom_billing"
alert_rule:
  - name: "cost_anomaly_30_percent"
    condition: "monthly_total > last_month_total * 1.3"
    severity: "WARN"
```

### Recommended Alert Thresholds

| Metric | Threshold | Window | Action |
|--------|----------|--------|--------|
| MoM cost increase | > 30% | Monthly | Review bills, identify driver |
| Resource package expiration | < 30 days | Daily | Renew or replace |
| RI coverage | < 70% | Weekly | Purchase additional RI |
| SP pool value | < 100 CNY | Daily | Top up savings plan |
| Account balance | < threshold | Real-time | Recharge to avoid service disruption |
