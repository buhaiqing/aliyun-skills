# Core Concepts — BSSOpenApi (Billing Management)

## Product Overview

BSSOpenApi (Billing Support System Open API) is Alibaba Cloud's unified billing management service. It provides programmatic access to account balances, bills, orders, resource packages, savings plans, RI utilization, transactions, and vouchers.

**Key characteristics:**
- **Region-independent:** Most operations default to `cn-hangzhou` as the API endpoint
- **BillingCycle format:** `YYYY-MM` (e.g., `2026-05`)
- **Timezone:** All timestamps are in **UTC+8 (Asia/Shanghai)**
- **API version:** `2017-12-14`
- **Endpoint:** `business.aliyuncs.com`

## Resource Architecture

### Billing Entities

```
Account
├── AccountBalance          # 账户余额 (credit + available + cash)
├── Bills                   # 账单体系
│   ├── BillOverview        # 月账单总览 (按产品汇总)
│   ├── Bill                # 账单明细 (按产品/按账号)
│   ├── InstanceBill        # 实例账单 (按资源实例)
│   ├── SettleBill          # 结算账单 (含 50,000+ 条目)
│   ├── AccountBill         # 账号账单 (按资源归属账号)
│   └── SplitItemBill       # 分账账单 (按分拆项)
├── Orders                  # 订单体系
│   ├── Orders              # 订单列表
│   └── OrderDetail         # 订单详情
├── Savings & Reservations  # 节省与预留
│   ├── SavingsPlans        # 储蓄计划
│   │   ├── Instance        # SP 实例信息
│   │   ├── DeductLog       # SP 抵扣记录
│   │   ├── UsageDetail     # SP 使用详情
│   │   └── CoverageDetail  # SP 覆盖详情
│   ├── ReservedInstances   # 预留实例
│   │   └── RIUtilization   # RI 使用率
│   └── ResourcePackages    # 资源包/SCU
│       └── Instances       # 资源包实例
├── Financial Tools         # 财务工具
│   ├── Transactions        # 交易流水
│   ├── PrepaidCards        # 储值卡
│   ├── CashCoupons         # 代金券
│   └── CostUnits           # 成本单元/财务单元
└── Price Queries           # 价格查询
    ├── PayAsYouGoPrice
    ├── SubscriptionPrice
    └── ResourcePackagePrice
```

### Dependency Graph

Billing operations are self-contained; they do not depend on other cloud resources. However:
- Bills reference `InstanceID` from product resources (ECS, RDS, etc.)
- Orders reference `ProductCode` and `ProductType`
- Savings Plans / RI reference `InstanceFamily` and `Region`

## Key Concepts

### BillingCycle
Format `YYYY-MM`, represents the accounting period. Bills are usually settled by day 3-5 of the following month.

### Pagination
Most query operations support:
- `PageNum` (default: 1)
- `PageSize` (default: 20, max: 100 for most APIs)
- `TotalCount` returned in response for total pages calculation

### Bill Granularity
| API | Granularity | Group By |
|-----|------------|----------|
| QueryBillOverview | Month | Product, SubscriptionType |
| QueryBill | Account-Level | ProductCode, BillOwnerId |
| QueryInstanceBill | Instance-Level | InstanceID, ProductCode |
| QuerySettleBill | Account-Level | ProductCode, BillOwnerId |
| QueryAccountBill | Account-Level | BillOwnerId |
| QuerySplitItemBill | Split-Item-Level | SplitItemID, Tag |

### Charge Types
| Code | Meaning |
|------|---------|
| `Subscription` | 包年包月 (Prepaid) |
| `PayAsYouGo` | 按量付费 (Postpaid) |
| `PrePaid` | 预付费 |

## Limits & Quotas

| Limit | Value |
|-------|-------|
| Bill history retention | 12 months (China site), 6 months (Intl) |
| Max PageSize for bills | 100 |
| QueryBillOverview date range | 1 month per call |
| Orders query default window | Last 1 hour (extendable with CreateTimeStart/End) |
| API rate limit | Varies by operation |

## Region Independence

All BSSOpenApi operations default to `cn-hangzhou`. The `RegionId` parameter, if present, is optional and defaults sensibly. However, some savings plan / RI queries do accept region filtering (`Region` parameter) to scope results.

## Security Model

### RAM Permissions
Minimum policy for read-only billing access:

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bssapi:Query*",
        "bssapi:Describe*",
        "bssapi:Get*"
      ],
      "Resource": "*"
    }
  ]
}
```

**Warning:** Billing APIs expose financial data. Grant with least privilege.

### Credential Masking (MANDATORY)
- NEVER log `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- Use existence checks: `test -n "$var" && echo "set"`
- JIT Go SDK: use `os.Getenv()` directly; avoid `fmt.Printf("%+v", config)`

## Billing Data Freshness

| Data Type | Freshness | Query Window |
|-----------|-----------|-------------|
| Account Balance | Real-time | Immediate |
| Bills (preliminary) | Daily update | Current month (incomplete) |
| Bills (final) | Day 3-5 next month | Prior month (complete) |
| RI/SCU Utilization | ~2 hour delay | Last 30 days |
| Savings Plans Usage | ~30 min delay | Last 30 days |
| Orders | Near real-time | Last 1 hour default |
| Transactions | ~5 min delay | Custom range |

### Single Point of Failure Analysis

- **API endpoint `business.aliyuncs.com`** — SPOF for all billing queries. No DR endpoint.
- **Credential compromise** — leaked AK/SK grants access to all financial data.
- **Mitigation:** Use STS temporary credentials for delegated billing access. Rotate keys every 90 days.
