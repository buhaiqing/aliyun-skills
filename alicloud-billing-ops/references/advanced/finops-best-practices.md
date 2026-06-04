# FinOps Best Practices — BSSOpenApi

## Overview

This document provides executable FinOps patterns using BSSOpenApi APIs. Each pattern includes CLI commands, alert criteria, and remediation steps.

## Pattern 1: Cost Anomaly Detection

### Problem
Monthly spend increased unexpectedly.

### Detection

```bash
#!/bin/bash
# Save as: check-cost-anomaly.sh
# Run: daily via cron

CURRENT_MONTH=$(date +%Y-%m)
LAST_MONTH=$(date -v-1m +%Y-%m 2>/dev/null || date -d '1 month ago' +%Y-%m)

CURRENT_TOTAL=$(aliyun bssopenapi QueryBillOverview --BillingCycle "$CURRENT_MONTH" 2>/dev/null | jq '[.Data.Items.Item[] | select(.PretaxAmount != null) | .PretaxAmount | tonumber] | add // 0')
LAST_TOTAL=$(aliyun bssopenapi QueryBillOverview --BillingCycle "$LAST_MONTH" 2>/dev/null | jq '[.Data.Items.Item[] | select(.PretaxAmount != null) | .PretaxAmount | tonumber] | add // 0')

if [ "$LAST_TOTAL" != "0" ] && [ -n "$CURRENT_TOTAL" ]; then
  CHANGE=$(python3 -c "print(f'{($CURRENT_TOTAL/$LAST_TOTAL - 1) * 100:.1f}')")
  ABS_CHANGE=$(python3 -c "print(abs(float('$CHANGE')))")
  if (( $(echo "$ABS_CHANGE > 30" | bc -l) )); then
    echo "[ALERT] Cost anomaly: ${CHANGE}% MoM change"
    echo "  Current: $CURRENT_TOTAL"
    echo "  Previous: $LAST_TOTAL"

    # Drill down by product
    aliyun bssopenapi QueryBillOverview --BillingCycle "$CURRENT_MONTH" | jq -r '.Data.Items.Item[] | [.ProductCode, .ProductName, .PretaxAmount] | @tsv' | sort -t$'\t' -k3 -rn | head -10
  fi
fi
```

### Alert Criteria
- MoM increase > 30% → P1 Alert
- MoM increase > 50% → P0 Alert
- New product appearing with > 1000 CNY → P1 Alert

### Remediation
1. Identify top spend driver using `QueryBillOverview` product breakdown
2. Dril down with `QueryBill` for product detail
3. Check for new or changed resources via `QueryInstanceBill`
4. Cross-reference with CloudMonitor for resource activity

## Pattern 2: Resource Expiration Warning

### Problem
Resource packages, RI, or subscriptions expiring without renewal causing pay-as-you-go surge.

### Detection

```bash
#!/bin/bash
# Save as: check-resource-expiry.sh
# Run: daily via cron

THRESHOLD_DAYS=30

echo "=== Resource Packages Expiring Within ${THRESHOLD_DAYS} Days ==="
aliyun bssopenapi QueryResourcePackageInstances --PageNum 1 --PageSize 100 | jq -r --argjson days "$THRESHOLD_DAYS" '
  .Data.Instances.Instance[] |
  select(.Status == "Valid") |
  select(
    (((.ExpiryTime | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime) - now) / 86400) <= $days
  ) |
  [.InstanceId, .PackageType, .RemainingAmount, .TotalAmount, .ExpiryTime] | @tsv
' | while IFS=$'\t' read id type remaining total expiry; do
  DAYS_LEFT=$(python3 -c "from datetime import datetime; d=datetime.strptime('$expiry','%Y-%m-%dT%H:%M:%SZ'); print((d-datetime.now()).days)")
  echo "[WARN] $type ($id): $remaining/$total units remaining, expires in $DAYS_LEFT days"
done

echo ""
echo "=== Savings Plans Ending ==="
aliyun bssopenapi QuerySavingsPlansInstance --PageNum 1 --PageSize 100 | jq -r '
  .Data.Items[] |
  select(.Status == "NORMAL") |
  select(
    (((.EndTime | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime) - now) / 86400) <= 30
  ) |
  [.InstanceId, .SavingsType, .CurrentPoolValue, .EndTime] | @tsv
' | while IFS=$'\t' read id type value endtime; do
  echo "[WARN] SP $id ($type): pool value $value, ends $endtime"
done
```

### Alert Criteria
- Resource package: remaining < 10% AND expiring in 30 days
- Savings Plan: end date within 30 days AND pool value < 100 CNY
- RI: end date within 30 days

### Remediation
1. Renew resource packages with similar or larger spec
2. Top up savings plans with appropriate commitment
3. Purchase new RI to maintain coverage
4. Evaluate if resource is still needed (could decommission instead of renewing)

## Pattern 3: RI/SCU Coverage Optimization

### Problem
Pay-as-you-go charges for resources that could be covered by RI or SCU.

### Detection

```bash
#!/bin/bash
# Save as: check-ri-coverage.sh
# Run: weekly via cron

echo "=== RI/SCU Coverage Check ==="

# Total coverage
COVERAGE=$(aliyun bssopenapi DescribeResourceCoverageTotal 2>/dev/null)
TOTAL_COV=$(echo "$COVERAGE" | jq -r '.Data.TotalCoverage.CoveragePercentage // "0"')
echo "Overall Coverage: ${TOTAL_COV}%"

if (( $(echo "$TOTAL_COV < 70" | bc -l) )); then
  echo ""
  echo "=== Uncovered Pay-As-You-Go Spend (RI-Eligible) ==="

  # Get pay-as-you-go ECS cost (RI-eligible)
  ECS_PAYGO=$(aliyun bssopenapi QueryBill --BillingCycle "$(date +%Y-%m)" --ProductCode "ecs" --SubscriptionType "PayAsYouGo" --PageNum 1 --PageSize 100 | jq '[.Data.Items.Item[].PretaxAmount | tonumber] | add // 0')

  if (( $(echo "$ECS_PAYGO > 100" | bc -l) )); then
    echo "ECS Pay-As-You-Go spend: $ECS_PAYGO CNY — consider purchasing ECS RI"
  fi
fi

# Per-resource coverage detail
echo ""
echo "=== Per-Product Coverage Detail ==="
aliyun bssopenapi DescribeResourceCoverageDetail --PageNum 1 --PageSize 20 2>/dev/null | jq -r '
  .Data.Items[] |
  [.CommodityCode, .CoveragePercentage, .TotalQuantity, .CapacityUnit] | @tsv
' | while IFS=$'\t' read code cov qty unit; do
  if (( $(echo "$cov < 80" | bc -l) )); then
    echo "[WARN] $code: ${cov}% covered ($qty $unit pay-as-you-go)"
  fi
done
```

### Alert Criteria
- Overall coverage < 70% → P1 Alert
- Per-product coverage < 50% → P0 Alert
- Pay-as-you-go spend > 1000 CNY/month on RI-eligible services

### Remediation
1. Use `DescribeResourceCoverageDetail` to identify specific uncovered products
2. Purchase RI matching the uncovered instance types
3. For ECS: match instance family, region, and quantity
4. For SCU: match storage type and region
5. Monitor coverage after purchase: check `DescribeResourceCoverageTotal` weekly

## Pattern 4: Savings Plans Optimization

### Problem
Savings plan pool depletion leading to pay-as-you-go charges.

### Detection

```bash
#!/bin/bash
# Save as: check-sp-optimization.sh
# Run: daily via cron

echo "=== Savings Plans Pool Status ==="
aliyun bssopenapi QuerySavingsPlansInstance --PageNum 1 --PageSize 100 | jq -r '
  .Data.Items[] |
  [.InstanceId, .SavingsType, .PaymentType, .Status, .CurrentPoolValue, .StartTime, .EndTime] | @tsv
' | while IFS=$'\t' read id type payment status value start end; do
  DAYS_LEFT=$(python3 -c "from datetime import datetime; d=datetime.strptime('$end','%Y-%m-%dT%H:%M:%SZ'); print((d-datetime.now()).days)")
  DAILY_RATE=$(( $(echo "$value" | sed 's/\..*//') / (${DAYS_LEFT:-1}) ))
  echo "SP $id: $type/$payment, pool=$value, ends in $DAYS_LEFT days (rate: ~$DAILY_RATE/day)"

  if (( $(echo "$value < 100" | bc -l) )) && [ "$status" = "NORMAL" ]; then
    echo "  ⚠️  Pool nearly depleted!"
  fi
done

# SP usage efficiency
echo ""
echo "=== Savings Plans Usage Efficiency ==="
aliyun bssopenapi DescribeSavingsPlansUsageTotal 2>/dev/null | jq -r '
  .Data.TotalUsage |
  [.SavingsRate, .UtilizationRate] |
  "Savings Rate: \(.[0])%, Utilization: \(.[1])%"
'

if (( $(echo "$UTIL > 95" | bc -l) )); then
  echo "⚠️  High SP utilization — consider increasing commitment"
fi
```

### Alert Criteria
- Pool value < 100 CNY → P1 Alert
- Days to depletion < 7 days → P0 Alert
- Utilization > 95% → P2 (consider increase)
- Utilization < 70% → P2 (over-committed)

### Remediation
1. Low pool: top up with additional savings plan purchase
2. High utilization: increase commitment amount
3. Low utilization: review if workload changed, adjust commitment

## Pattern 5: Budget Alert

### Problem
No automated budget tracking.

### Detection

```bash
#!/bin/bash
# Save as: budget-check.sh
# Run: daily via cron

BUDGET=${BUDGET_LIMIT:-10000}  # Default 10,000 CNY/month

echo "=== Budget Check: ${BUDGET} CNY/month ==="

CURRENT_TOTAL=$(aliyun bssopenapi QueryBillOverview --BillingCycle "$(date +%Y-%m)" 2>/dev/null | jq '[.Data.Items.Item[] | select(.PretaxAmount != null) | .PretaxAmount | tonumber] | add // 0')
BALANCE=$(aliyun bssopenapi QueryAccountBalance 2>/dev/null | jq -r '.Data.AvailableAmount // "0"')

PCT=$(python3 -c "print(f'{($CURRENT_TOTAL / $BUDGET) * 100:.1f}')")

echo "Current spend: $CURRENT_TOTAL CNY (${PCT}% of budget)"
echo "Available balance: $BALANCE CNY"

if (( $(echo "$CURRENT_TOTAL > $BUDGET * 0.8" | bc -l) )); then
  echo "[WARN] Budget ${PCT}% consumed — projected to exceed budget"
fi

if (( $(echo "$BALANCE < $CURRENT_TOTAL" | bc -l) )); then
  echo "[CRITICAL] Available balance less than current spend — risk of service disruption"
fi
```

### Alert Criteria
- 80% consumed → P2 (informational)
- 90% consumed → P1 (warning)
- 100% consumed → P0 (critical)
- Balance < projected spend → P0 (critical)

## Pattern 6: Account Health Check

### Problem
No regular account financial health assessment.

### Execution

```bash
#!/bin/bash
# Save as: account-health-check.sh
# Run: weekly via cron

echo "=== Account Financial Health Report ==="
echo "Generated: $(date)"

# Balance
echo ""
echo "--- Balance ---"
aliyun bssopenapi QueryAccountBalance | jq '{Available: .Data.AvailableAmount, Credit: .Data.CreditAmount, Currency: .Data.Currency}'

# Current month spend
echo ""
echo "--- Current Month Spend (Top 5) ---"
aliyun bssopenapi QueryBillOverview --BillingCycle "$(date +%Y-%m)" | jq -r '.Data.Items.Item[] | [.ProductCode, .ProductName, .PretaxAmount] | @tsv' | sort -t$'\t' -k3 -rn | head -5

# Active orders
echo ""
echo "--- Recent Orders ---"
aliyun bssopenapi QueryOrders --PageNum 1 --PageSize 5 2>/dev/null | jq -r '.Data.OrderList.Order[] | [.OrderId, .ProductCode, .PaymentStatus, .CreateTime] | @tsv'

# Resource packages
echo ""
echo "--- Active Resource Packages ---"
aliyun bssopenapi QueryResourcePackageInstances --PageNum 1 --PageSize 100 | jq -r '.Data.Instances.Instance[] | select(.Status=="Valid") | [.InstanceId, .PackageType, .RemainingAmount, .TotalAmount] | @tsv'

# Coupons and cards
echo ""
echo "--- Coupons ---"
aliyun bssopenapi QueryCashCoupons | jq -r '.Data.CashCoupon[] | select(.Status=="Available") | [.CashCouponId, .NominalValue, .Balance, .EffectiveTime, .ExpiryTime] | @tsv'

echo ""
echo "--- Prepaid Cards ---"
aliyun bssopenapi QueryPrepaidCards | jq -r '.Data.PrepaidCard[] | [.PrepaidCardId, .NominalValue, .Balance, .ExpiryTime] | @tsv'

echo ""
echo "--- Savings Plans ---"
aliyun bssopenapi QuerySavingsPlansInstance --PageNum 1 --PageSize 100 | jq -r '.Data.Items[] | [.InstanceId, .SavingsType, .CurrentPoolValue, .Status] | @tsv'
```

## Summary: FinOps Maturity Ladder

| Level | Practices | Status |
|-------|----------|--------|
| L1 - Crawl | QueryAccountBalance + QueryBillOverview | Covered |
| L2 - Walk | Cost anomaly detection, budget alerts, resource expiry | Covered |
| L3 - Run | RI/SP optimization, split billing, tag-based allocation | Covered |
| L4 - Fly | Automated FinOps pipeline, ML-based anomaly, multi-cloud | Future |
