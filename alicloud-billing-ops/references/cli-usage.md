# CLI — BSSOpenApi (`aliyun bssopenapi`)

## Conventions (agent execution)

- Output is **JSON by default** — NO `--output json` needed
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- All billing operations use endpoint `business.aliyuncs.com`
- BillingCycle format: `YYYY-MM` (e.g., `2026-05`)
- Region default: `cn-hangzhou` (most billing APIs don't require region)

## CLI vs API Coverage

All 15 core operations in this skill are fully covered by `aliyun bssopenapi` CLI. No SDK-only gaps for core billing queries.

| Operation (API) | CLI Command | Status |
|-----------------|-------------|--------|
| QueryAccountBalance | `aliyun bssopenapi QueryAccountBalance` | full |
| QueryBillOverview | `aliyun bssopenapi QueryBillOverview --BillingCycle 2026-05` | full |
| QueryBill | `aliyun bssopenapi QueryBill --BillingCycle 2026-05 --PageNum 1 --PageSize 20` | full |
| QueryInstanceBill | `aliyun bssopenapi QueryInstanceBill --BillingCycle 2026-05 --PageNum 1 --PageSize 20` | full |
| QuerySettleBill | `aliyun bssopenapi QuerySettleBill --BillingCycle 2026-05 --PageNum 1 --PageSize 100` | full |
| QueryAccountBill | `aliyun bssopenapi QueryAccountBill --BillingCycle 2026-05 --PageNum 1 --PageSize 20` | full |
| QuerySplitItemBill | `aliyun bssopenapi QuerySplitItemBill --BillingCycle 2026-05 --PageNum 1 --PageSize 20` | full |
| QueryOrders | `aliyun bssopenapi QueryOrders --CreateTimeStart 2026-05-01T00:00:00Z --CreateTimeEnd 2026-05-31T23:59:59Z` | full |
| GetOrderDetail | `aliyun bssopenapi GetOrderDetail --OrderId 1234567890` | full |
| QueryRIUtilizationDetail | `aliyun bssopenapi QueryRIUtilizationDetail --PageNum 1 --PageSize 20` | full |
| QuerySavingsPlansInstance | `aliyun bssopenapi QuerySavingsPlansInstance --PageNum 1 --PageSize 20` | full |
| QuerySavingsPlansDeductLog | `aliyun bssopenapi QuerySavingsPlansDeductLog --InstanceId sp-xxxxx --StartTime 2026-05-01T00:00:00Z --EndTime 2026-05-31T23:59:59Z` | full |
| QueryResourcePackageInstances | `aliyun bssopenapi QueryResourcePackageInstances --PageNum 1 --PageSize 20` | full |
| QueryAccountTransactions | `aliyun bssopenapi QueryAccountTransactions --PageNum 1 --PageSize 20` | full |
| QueryPrepaidCards | `aliyun bssopenapi QueryPrepaidCards` | full |
| QueryCashCoupons | `aliyun bssopenapi QueryCashCoupons` | full |

## Command Map — Core Operations

### 1. QueryAccountBalance — 账户余额

```bash
# Get account balance (no params needed)
aliyun bssopenapi QueryAccountBalance

# Extract specific fields with JMESPath
# JSON paths: $.Data.AvailableAmount, $.Data.CreditAmount, $.Data.Currency, $.Data.MybankCreditAmount
```

### 2. QueryBillOverview — 账单总览

```bash
# Monthly bill overview
aliyun bssopenapi QueryBillOverview \
  --BillingCycle "2026-05"

# JSON paths:
# $.Data.BillOwnerId, $.Data.BillAccountName, $.Data.BillType
# $.Data.Items.Item[]: {ProductCode, ProductName, PretaxAmount, BillingCycle}
```

### 3. QueryBill — 账单明细

```bash
# Bill details by product
aliyun bssopenapi QueryBill \
  --BillingCycle "2026-05" \
  --PageNum 1 \
  --PageSize 20 \
  --ProductCode "ecs"

# JSON paths:
# $.Data.TotalCount, $.Data.BillingCycle
# $.Data.Items.Item[]: {RecordID, ProductCode, UsageStartTime, UsageEndTime, PretaxAmount, Currency}
```

### 4. QueryInstanceBill — 实例账单

```bash
# Instance-level billing
aliyun bssopenapi QueryInstanceBill \
  --BillingCycle "2026-05" \
  --PageNum 1 \
  --PageSize 20 \
  --IsBillingItem false

# JSON paths:
# $.Data.Items.Item[]: {InstanceID, ProductCode, ProductName, PretaxAmount, BillingType}
```

### 5. QuerySettleBill — 结算账单

```bash
# Settled bill (supports large datasets > 50K rows)
aliyun bssopenapi QuerySettleBill \
  --BillingCycle "2026-05" \
  --PageNum 1 \
  --PageSize 100

# JSON paths:
# $.Data.TotalCount, $.Data.BillingCycle
# $.Data.Items.Item[]: {RecordID, ProductCode, PretaxAmount, UsageStartTime}
```

### 6. QueryAccountBill — 账号账单

```bash
# Account-level bill grouped by bill owner
aliyun bssopenapi QueryAccountBill \
  --BillingCycle "2026-05" \
  --PageNum 1 \
  --PageSize 20

# JSON paths:
# $.Data.Items.Item[]: {BillAccountName, PretaxAmount, Currency}
```

### 7. QuerySplitItemBill — 分账账单

```bash
# Split item billing
aliyun bssopenapi QuerySplitItemBill \
  --BillingCycle "2026-05" \
  --PageNum 1 \
  --PageSize 20

# JSON paths:
# $.Data.Items.Item[]: {SplitItemID, SplitItemName, PretaxAmount, ProductCode, Tag}
```

### 8. QueryOrders + GetOrderDetail — 订单查询

```bash
# Query orders in time range
aliyun bssopenapi QueryOrders \
  --CreateTimeStart "2026-05-01T00:00:00Z" \
  --CreateTimeEnd "2026-05-15T23:59:59Z" \
  --PageNum 1 \
  --PageSize 20

# Get specific order detail
aliyun bssopenapi GetOrderDetail \
  --OrderId "1234567890"

# JSON paths (Orders):
# $.Data.OrderList.Order[]: {OrderId, ProductCode, CreateTime, PaymentStatus, PaymentTime, PretaxAmount}
# JSON paths (OrderDetail):
# $.Data.OrderId, $.Data.CreateTime, $.Data.PaymentStatus, $.Data.PaymentTime, $.Data.OriginalConfig
```

### 9. QueryRIUtilizationDetail — RI利用率

```bash
# RI utilization details
aliyun bssopenapi QueryRIUtilizationDetail \
  --PageNum 1 \
  --PageSize 20 \
  --DeductedCommodityCode "ecs"

# JSON paths:
# $.Data.Items[]: {RIInstanceId, InstanceSpec, DeductedCommodityCode, DeductedInstanceId,
#   DeductFactorTotal, RIUtilizationRatio}
```

### 10. QuerySavingsPlansInstance + QuerySavingsPlansDeductLog

```bash
# List savings plans
aliyun bssopenapi QuerySavingsPlansInstance \
  --PageNum 1 \
  --PageSize 20

# Savings plan deduction log
aliyun bssopenapi QuerySavingsPlansDeductLog \
  --InstanceId "sp-xxxxxxxx" \
  --StartTime "2026-05-01T00:00:00Z" \
  --EndTime "2026-05-31T23:59:59Z"

# JSON paths (Instance):
# $.Data.Items[]: {InstanceId, SavingsType, PaymentType, Status, CurrentPoolValue,
#   StartTime, EndTime, Region, InstanceFamily}
# JSON paths (DeductLog):
# $.Data.Items[]: {SavingsType, StartTime, EndTime, BillModule, OwnerId, EndTime, InstanceId}
```

### 11. QueryResourcePackageInstances — 资源包

```bash
# Query resource packages
aliyun bssopenapi QueryResourcePackageInstances \
  --PageNum 1 \
  --PageSize 20

# JSON paths:
# $.Data.Instances.Instance[]: {InstanceId, PackageType, Status, TotalAmount,
#   RemainingAmount, EffectiveTime, ExpiryTime}
```

### 12. QueryAccountTransactions — 交易流水

```bash
# Transaction records
aliyun bssopenapi QueryAccountTransactions \
  --PageNum 1 \
  --PageSize 20

# JSON paths:
# $.Data.AccountTransactionsList.AccountTransactionsList[]:
#   {TransactionNumber, Amount, Balance, TransactionAccount, TransactionChannel, TransactionTime}
```

### 13. QueryPrepaidCards — 储值卡

```bash
# Prepaid cards
aliyun bssopenapi QueryPrepaidCards

# JSON paths:
# $.Data.PrepaidCard[]: {PrepaidCardId, PrepaidCardNo, Status, NominalValue,
#   Balance, EffectiveTime, ExpiryTime}
```

### 14. QueryCashCoupons — 代金券

```bash
# Cash coupons (vouchers)
aliyun bssopenapi QueryCashCoupons

# JSON paths:
# $.Data.CashCoupon[]: {CashCouponId, CashCouponNo, Status, NominalValue,
#   Balance, EffectiveTime, ExpiryTime}
```

## Pagination Pattern

```bash
# Fetch all pages with loop
PAGE=1
PAGE_SIZE=100
while true; do
  RESPONSE=$(aliyun bssopenapi QueryBill \
    --BillingCycle "2026-05" \
    --PageNum $PAGE \
    --PageSize $PAGE_SIZE)

  TOTAL=$(echo "$RESPONSE" | jq -r '.Data.TotalCount')
  TOTAL_PAGES=$(( (TOTAL + PAGE_SIZE - 1) / PAGE_SIZE ))

  echo "$RESPONSE" | jq '.Data.Items.Item[]'

  if [ $PAGE -ge $TOTAL_PAGES ]; then break; fi
  PAGE=$((PAGE + 1))
done
```

## Cost Anomaly Detection (FinOps)

### Monthly-over-Month Comparison

```bash
# Compare current month vs last month
aliyun bssopenapi QueryBillOverview --BillingCycle "2026-05" | jq -r '.Data.Items.Item[] | [.ProductCode, .PretaxAmount] | @tsv' > /tmp/bill_2026-05.tsv
aliyun bssopenapi QueryBillOverview --BillingCycle "2026-04" | jq -r '.Data.Items.Item[] | [.ProductCode, .PretaxAmount] | @tsv' > /tmp/bill_2026-04.tsv

# Join and detect >30% increase
join -t $'\t' -a 1 /tmp/bill_2026-05.tsv /tmp/bill_2026-04.tsv | \
  awk -F'\t' 'NF==4 && $2>0 && $4>0 && ($2/$4 - 1) > 0.3 {printf "%s: %.2f -> %.2f (+%.0f%%)\n", $1, $4, $2, ($2/$4-1)*100}'
```

### Resource Expiration Warning (30 days)

```bash
# Check resource packages expiring within 30 days
aliyun bssopenapi QueryResourcePackageInstances --PageNum 1 --PageSize 100 | \
  jq -r '.Data.Instances.Instance[] | select(.Status=="Valid") | [.InstanceId, .PackageType, .ExpiryTime] | @tsv' | \
  while read id type expiry; do
    DAYS_LEFT=$(( ($(date -d "$expiry" +%s) - $(date +%s)) / 86400 ))
    if [ "$DAYS_LEFT" -le 30 ]; then
      echo "$id ($type) expires in $DAYS_LEFT days on $expiry"
    fi
  done
```

## Common JSON Paths (Centralized)

```
QueryAccountBalance:
  $.Data.{AvailableAmount, CreditAmount, Currency}

QueryBillOverview:
  $.Data.Items.Item[]: {ProductCode, ProductName, PretaxAmount, BillingCycle}

QueryBill / QuerySettleBill:
  $.Data.{TotalCount, BillingCycle}
  $.Data.Items.Item[]: {RecordID, ProductCode, UsageStartTime, UsageEndTime, PretaxAmount, Currency}

QueryInstanceBill:
  $.Data.Items.Item[]: {InstanceID, ProductCode, ProductName, PretaxAmount, BillingType}

QuerySplitItemBill:
  $.Data.Items.Item[]: {SplitItemID, SplitItemName, PretaxAmount, ProductCode, Tag}

QueryOrders:
  $.Data.OrderList.Order[]: {OrderId, ProductCode, CreateTime, PaymentStatus, PretaxAmount}

GetOrderDetail:
  $.Data.{OrderId, CreateTime, PaymentStatus, PaymentTime, OriginalConfig}

QueryRIUtilizationDetail:
  $.Data.Items[]: {RIInstanceId, InstanceSpec, DeductedInstanceId, RIUtilizationRatio}

QuerySavingsPlansInstance:
  $.Data.Items[]: {InstanceId, SavingsType, PaymentType, Status, CurrentPoolValue, StartTime, EndTime}

QuerySavingsPlansDeductLog:
  $.Data.Items[]: {SavingsType, StartTime, EndTime, BillModule, InstanceId}

QueryResourcePackageInstances:
  $.Data.Instances.Instance[]: {InstanceId, PackageType, Status, TotalAmount, RemainingAmount, EffectiveTime, ExpiryTime}

QueryAccountTransactions:
  $.Data.AccountTransactionsList.AccountTransactionsList[]: {TransactionNumber, Amount, Balance, TransactionChannel, TransactionTime}

QueryPrepaidCards:
  $.Data.PrepaidCard[]: {PrepaidCardId, PrepaidCardNo, Status, NominalValue, Balance, EffectiveTime, ExpiryTime}

QueryCashCoupons:
  $.Data.CashCoupon[]: {CashCouponId, CashCouponNo, Status, NominalValue, Balance, EffectiveTime, ExpiryTime}
```

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Items.Item[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun ecs DescribeInstances --PageSize 50 | jq '{total: .TotalCount, items: [.Items.Item[]? | {id: .Id, name: .Name}]}'
```

