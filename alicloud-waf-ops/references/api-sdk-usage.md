# API & SDK — Alibaba Cloud WAF

## OpenAPI

- **Spec:** WAF OpenAPI 2021-10-01
- **Style:** RPC
- **Documentation:** https://help.aliyun.com/zh/waf/web-application-firewall-3-0/developer-reference/api-overview
- **Endpoint:** `waf-openapi.{region}.aliyuncs.com`

## SDK Operations Map

| Goal | OperationId | SDK Method | CLI Command |
|------|-------------|------------|-------------|
| **Instance Management** | | | |
| Query instance info | DescribeInstanceInfo | DescribeInstanceInfo | `DescribeInstanceInfo` |
| Query instance edition | DescribeInstanceEdition | DescribeInstanceEdition | `DescribeInstanceEdition` |
| **Domain Protection** | | | |
| Add domain | CreateDomain | CreateDomain | `CreateDomain` |
| List domains | DescribeDomainList | DescribeDomainList | `DescribeDomainList` |
| Query domain | DescribeDomainDetail | DescribeDomainDetail | `DescribeDomainDetail` |
| Update domain | ModifyDomain | ModifyDomain | `ModifyDomain` |
| Delete domain | DeleteDomain | DeleteDomain | `DeleteDomain` |
| **Access Control** | | | |
| List ACL rules | DescribeAccessControlList | DescribeAccessControlList | `DescribeAccessControlList` |
| Create ACL rule | CreateAccessControl | CreateAccessControl | `CreateAccessControl` |
| Update ACL rule | ModifyAccessControl | ModifyAccessControl | `ModifyAccessControl` |
| Delete ACL rule | DeleteAccessControl | DeleteAccessControl | `DeleteAccessControl` |
| **Defense Rules** | | | |
| List defense rules | DescribeDefenseRules | DescribeDefenseRules | `DescribeDefenseRules` |
| Create defense rule | CreateDefenseRule | CreateDefenseRule | `CreateDefenseRule` |
| Update defense rule | ModifyDefenseRule | ModifyDefenseRule | `ModifyDefenseRule` |
| Delete defense rule | DeleteDefenseRule | DeleteDefenseRule | `DeleteDefenseRule` |
| **Traffic Analysis** | | | |
| Top IPs | DescribeVisitTopIp | DescribeVisitTopIp | `DescribeVisitTopIp` |
| Top URLs | DescribeVisitTopUrl | DescribeVisitTopUrl | `DescribeVisitTopUrl` |
| IP blacklist hits | DescribeIpHitItems | DescribeIpHitItems | `DescribeIpHitItems` |
| **Logging** | | | |
| Log status | DescribeLogStatus | DescribeLogStatus | `DescribeLogStatus` |
| Configure logging | ModifyLogStatus | ModifyLogStatus | `ModifyLogStatus` |

## Request / Response Notes

### Required Fields

| Operation | Required Fields |
|-----------|-----------------|
| DescribeInstanceInfo | RegionId |
| CreateDomain | RegionId, InstanceId, Domain, ListenPorts, OriginAddress |
| DescribeDomainList | RegionId, InstanceId |
| CreateAccessControl | RegionId, InstanceId, Domain, RuleName, Action, Ip |
| CreateDefenseRule | RegionId, InstanceId, Domain, RuleName, RuleType, DefenseType |
| DescribeVisitTopIp | RegionId, InstanceId, Domain, StartTimestamp, EndTimestamp |

### Pagination

- **PageNumber / PageSize:** Standard page-based pagination
- **NextToken:** Token-based pagination for large result sets

```bash
# Page-based pagination example
aliyun waf-openapi DescribeDomainList \
  --RegionId cn-hangzhou \
  --InstanceId waf_xxx \
  --PageNumber 1 \
  --PageSize 20 \
  --version 2021-10-01 \
  --force
```

### Timestamp Format

- All timestamps are in **epoch seconds** (Unix timestamp)
- Example: `1665331200` = 2022-10-09 00:00:00 UTC

## Common Response Fields

| Field | Type | Description |
|-------|------|-------------|
| RequestId | string | Unique request identifier |
| Success | boolean | Whether request succeeded |
| Code | string | Error code (on failure) |
| Message | string | Error message (on failure) |

## SDK Package Reference

| Language | Package |
|----------|---------|
| Go | `github.com/alibabacloud-go/waf-openapi-20211001/v2/client` |
| Python | `alibabacloud_waf_openapi20211001` |
| Java | `com.aliyun.waf-openapi20211001` |

## JIT Go SDK Example

```go
package main

import (
    "fmt"
    "os"
    
    openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
    "github.com/alibabacloud-go/tea/tea"
    waf "github.com/alibabacloud-go/waf-openapi-20211001/v2/client"
)

func main() {
    config := &openapi.Config{
        AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
        Endpoint:        tea.String("waf-openapi.cn-hangzhou.aliyuncs.com"),
    }
    
    client, err := waf.NewClient(config)
    if err != nil {
        panic(err)
    }
    
    request := &waf.DescribeInstanceInfoRequest{
        RegionId: tea.String("cn-hangzhou"),
    }
    
    response, err := client.DescribeInstanceInfo(request)
    if err != nil {
        panic(err)
    }
    
    fmt.Println(tea.ToString(response.Body))
}
```
