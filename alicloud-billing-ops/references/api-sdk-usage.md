# API & SDK — BSSOpenApi

## OpenAPI

- **Spec:** BSSOpenApi 2017-12-14
- **Endpoint:** `business.aliyuncs.com`
- **Region:** Default `cn-hangzhou` (billing is region-independent)
- **Protocol:** HTTPS only

## Go SDK

### Package

```go
import bssopenapi "github.com/alibabacloud-go/bssopenapi-20171214/v3/client"
```

### Client Initialization

```go
package main

import (
    "fmt"
    "os"

    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    bssopenapi "github.com/alibabacloud-go/bssopenapi-20171214/v3/client"
    "github.com/alibabacloud-go/tea/tea"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("business.aliyuncs.com"),
    }

    client, err := bssopenapi.NewClient(config)
    if err != nil {
        panic(err)
    }

    // Operation-specific calls below
}
```

## Operations Map

| Goal | API Operation | SDK Method | Required Fields |
|------|--------------|------------|----------------|
| Account Balance | QueryAccountBalance | client.QueryAccountBalance() | None |
| Bill Overview | QueryBillOverview | client.QueryBillOverview() | BillingCycle |
| Bill Detail | QueryBill | client.QueryBill() | BillingCycle |
| Instance Bill | QueryInstanceBill | client.QueryInstanceBill() | BillingCycle |
| Settle Bill | QuerySettleBill | client.QuerySettleBill() | BillingCycle |
| Account Bill | QueryAccountBill | client.QueryAccountBill() | BillingCycle |
| Split Bill | QuerySplitItemBill | client.QuerySplitItemBill() | BillingCycle |
| Orders | QueryOrders | client.QueryOrders() | CreateTimeStart, CreateTimeEnd |
| Order Detail | GetOrderDetail | client.GetOrderDetail() | OrderId |
| RI Utilization | QueryRIUtilizationDetail | client.QueryRIUtilizationDetail() | None |
| Savings Plans | QuerySavingsPlansInstance | client.QuerySavingsPlansInstance() | None |
| SP Deduction | QuerySavingsPlansDeductLog | client.QuerySavingsPlansDeductLog() | InstanceId, StartTime, EndTime |
| Resource Packages | QueryResourcePackageInstances | client.QueryResourcePackageInstances() | None |
| Transactions | QueryAccountTransactions | client.QueryAccountTransactions() | None |
| Prepaid Cards | QueryPrepaidCards | client.QueryPrepaidCards() | None |
| Cash Coupons | QueryCashCoupons | client.QueryCashCoupons() | None |

## Pagination

All list operations support pagination:

```go
request := &bssopenapi.QueryBillRequest{
    BillingCycle: tea.String("2026-05"),
    PageNum:      tea.Int32(1),
    PageSize:     tea.Int32(100),
}

response, err := client.QueryBill(request)
totalCount := tea.Int32Value(response.Body.Data.TotalCount)
pageSize := tea.Int32Value(response.Body.Data.PageSize)
totalPages := (totalCount + pageSize - 1) / pageSize
```

## Request/Response Notes

### QueryBill (typical pattern)

**Request:**
```go
request := &bssopenapi.QueryBillRequest{
    BillingCycle: tea.String("2026-05"),
    PageNum:      tea.Int32(1),
    PageSize:     tea.Int32(20),
    ProductCode:  tea.String("ecs"),          // optional filter
    SubscriptionType: tea.String("PayAsYouGo"), // optional
    IsHideZeroCharge: tea.Bool(true),           // optional
}
```

**Response Fields:**
```go
response.Body.Data.{BillingCycle, AccountID, TotalCount}
response.Body.Data.Items.Item[]: {RecordID, ProductCode, ProductName, SubscriptionType,
  InstanceID, UsageStartTime, UsageEndTime, PretaxAmount, Currency}
```

### QueryAccountBalance

**Response Fields:**
```go
response.Body.Data.{AvailableAmount, CreditAmount, Currency, MybankCreditAmount}
```

### QueryOrders

**Request:**
```go
request := &bssopenapi.QueryOrdersRequest{
    CreateTimeStart: tea.String("2026-05-01T00:00:00Z"),
    CreateTimeEnd:   tea.String("2026-05-31T23:59:59Z"),
    PageNum:         tea.Int32(1),
    PageSize:        tea.Int32(20),
    OrderType:       tea.String("New"), // New/Renew/Upgrade
    PaymentStatus:   tea.String("Paid"), // Unpaid/Paid/Cancelled
}
```

### QueryRIUtilizationDetail

**Request:**
```go
request := &bssopenapi.QueryRIUtilizationDetailRequest{
    PageNum:                tea.Int32(1),
    PageSize:               tea.Int32(20),
    DeductedCommodityCode:  tea.String("ecs"),
    RICommodityCode:        tea.String("ecs"),
}
```

### QuerySavingsPlansDeductLog

**Request:**
```go
request := &bssopenapi.QuerySavingsPlansDeductLogRequest{
    InstanceId: tea.String("sp-xxxxxxxx"),
    StartTime:  tea.String("2026-05-01T00:00:00Z"),
    EndTime:    tea.String("2026-05-31T23:59:59Z"),
    PageNum:    tea.Int32(1),
    PageSize:   tea.Int32(20),
}
```

## JIT SDK Workflow

```bash
# Initialize workspace
mkdir -p /tmp/aliyun-sdk-workspace
cd /tmp/aliyun-sdk-workspace
go mod init sdk-script
export GOPROXY="https://goproxy.cn,direct"

# Get dependencies
go get github.com/alibabacloud-go/darabonba-openapi/v2/client
go get github.com/alibabacloud-go/tea
go get github.com/alibabacloud-go/bssopenapi-20171214/v3/client

# Run script
go run ./main.go
```

## Error Handling Pattern

```go
response, err := client.QueryBill(request)
if err != nil {
    // Check for SDK error
    if sdkErr, ok := err.(*tea.SDKError); ok {
        code := tea.StringValue(sdkErr.Code)
        if code == "Throttling.User" {
            // Retry with backoff
        } else if code == "NotAuthorized" {
            // HALT: check RAM permissions
        }
    }
    panic(err)
}

// Check business error in response
if tea.BoolValue(response.Body.Success) == false {
    code := tea.StringValue(response.Body.Code)
    message := tea.StringValue(response.Body.Message)
    // Handle per error taxonomy
}
```

## SDK Package Naming

| Product | Go SDK Package |
|---------|---------------|
| BSSOpenApi | `github.com/alibabacloud-go/bssopenapi-20171214/v3/client` |

> Find latest versions at: https://github.com/alibabacloud-go
