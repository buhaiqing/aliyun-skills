# API & SDK — Alibaba Cloud SLB (Classic Load Balancer)

## OpenAPI

- **Product**: Slb
- **Version**: 2014-05-15
- **Style**: RPC
- **Endpoint**: `slb.aliyuncs.com` (global), or region-specific endpoints
- **Docs**: https://www.alibabacloud.com/help/en/slb
- **API Explorer**: https://api.aliyun.com/api/Slb/2014-05-15

## SDK Operations Map

### Instance Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create instance | CreateLoadBalancer | `CreateLoadBalancer` | `aliyun slb CreateLoadBalancer` |
| Describe instances | DescribeLoadBalancers | `DescribeLoadBalancers` | `aliyun slb DescribeLoadBalancers` |
| Describe attribute | DescribeLoadBalancerAttribute | `DescribeLoadBalancerAttribute` | `aliyun slb DescribeLoadBalancerAttribute` |
| Set status | SetLoadBalancerStatus | `SetLoadBalancerStatus` | `aliyun slb SetLoadBalancerStatus` |
| Set name | SetLoadBalancerName | `SetLoadBalancerName` | `aliyun slb SetLoadBalancerName` |
| Modify spec | ModifyLoadBalancerInstanceSpec | `ModifyLoadBalancerInstanceSpec` | `aliyun slb ModifyLoadBalancerInstanceSpec` |
| Delete instance | DeleteLoadBalancer | `DeleteLoadBalancer` | `aliyun slb DeleteLoadBalancer` |
| Set delete protection | SetLoadBalancerDeleteProtection | `SetLoadBalancerDeleteProtection` | `aliyun slb SetLoadBalancerDeleteProtection` |
| Set modification protection | SetLoadBalancerModificationProtection | `SetLoadBalancerModificationProtection` | `aliyun slb SetLoadBalancerModificationProtection` |

### Listener Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create TCP listener | CreateLoadBalancerTCPListener | `CreateLoadBalancerTCPListener` | `aliyun slb CreateLoadBalancerTCPListener` |
| Create UDP listener | CreateLoadBalancerUDPListener | `CreateLoadBalancerUDPListener` | `aliyun slb CreateLoadBalancerUDPListener` |
| Create HTTP listener | CreateLoadBalancerHTTPListener | `CreateLoadBalancerHTTPListener` | `aliyun slb CreateLoadBalancerHTTPListener` |
| Create HTTPS listener | CreateLoadBalancerHTTPSListener | `CreateLoadBalancerHTTPSListener` | `aliyun slb CreateLoadBalancerHTTPSListener` |
| Describe listeners | DescribeLoadBalancerListeners | `DescribeLoadBalancerListeners` | `aliyun slb DescribeLoadBalancerListeners` |
| Describe TCP attribute | DescribeLoadBalancerTCPListenerAttribute | `DescribeLoadBalancerTCPListenerAttribute` | `aliyun slb DescribeLoadBalancerTCPListenerAttribute` |
| Describe UDP attribute | DescribeLoadBalancerUDPListenerAttribute | `DescribeLoadBalancerUDPListenerAttribute` | `aliyun slb DescribeLoadBalancerUDPListenerAttribute` |
| Describe HTTP attribute | DescribeLoadBalancerHTTPListenerAttribute | `DescribeLoadBalancerHTTPListenerAttribute` | `aliyun slb DescribeLoadBalancerHTTPListenerAttribute` |
| Describe HTTPS attribute | DescribeLoadBalancerHTTPSListenerAttribute | `DescribeLoadBalancerHTTPSListenerAttribute` | `aliyun slb DescribeLoadBalancerHTTPSListenerAttribute` |
| Set TCP attribute | SetLoadBalancerTCPListenerAttribute | `SetLoadBalancerTCPListenerAttribute` | `aliyun slb SetLoadBalancerTCPListenerAttribute` |
| Set UDP attribute | SetLoadBalancerUDPListenerAttribute | `SetLoadBalancerUDPListenerAttribute` | `aliyun slb SetLoadBalancerUDPListenerAttribute` |
| Set HTTP attribute | SetLoadBalancerHTTPListenerAttribute | `SetLoadBalancerHTTPListenerAttribute` | `aliyun slb SetLoadBalancerHTTPListenerAttribute` |
| Set HTTPS attribute | SetLoadBalancerHTTPSListenerAttribute | `SetLoadBalancerHTTPSListenerAttribute` | `aliyun slb SetLoadBalancerHTTPSListenerAttribute` |
| Delete listener | DeleteLoadBalancerListener | `DeleteLoadBalancerListener` | `aliyun slb DeleteLoadBalancerListener` |
| Start listener | StartLoadBalancerListener | `StartLoadBalancerListener` | `aliyun slb StartLoadBalancerListener` |
| Stop listener | StopLoadBalancerListener | `StopLoadBalancerListener` | `aliyun slb StopLoadBalancerListener` |

### VServer Group Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create group | CreateVServerGroup | `CreateVServerGroup` | `aliyun slb CreateVServerGroup` |
| Describe groups | DescribeVServerGroups | `DescribeVServerGroups` | `aliyun slb DescribeVServerGroups` |
| Describe attribute | DescribeVServerGroupAttribute | `DescribeVServerGroupAttribute` | `aliyun slb DescribeVServerGroupAttribute` |
| Add backend servers | AddVServerGroupBackendServers | `AddVServerGroupBackendServers` | `aliyun slb AddVServerGroupBackendServers` |
| Remove backend servers | RemoveVServerGroupBackendServers | `RemoveVServerGroupBackendServers` | `aliyun slb RemoveVServerGroupBackendServers` |
| Modify backend servers | ModifyVServerGroupBackendServers | `ModifyVServerGroupBackendServers` | `aliyun slb ModifyVServerGroupBackendServers` |
| Set group attribute | SetVServerGroupAttribute | `SetVServerGroupAttribute` | `aliyun slb SetVServerGroupAttribute` |
| Delete group | DeleteVServerGroup | `DeleteVServerGroup` | `aliyun slb DeleteVServerGroup` |

### Backend Server Operations (Default Group)

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Add backend servers | AddBackendServers | `AddBackendServers` | `aliyun slb AddBackendServers` |
| Remove backend servers | RemoveBackendServers | `RemoveBackendServers` | `aliyun slb RemoveBackendServers` |
| Set backend servers | SetBackendServers | `SetBackendServers` | `aliyun slb SetBackendServers` |
| Describe health status | DescribeHealthStatus | `DescribeHealthStatus` | `aliyun slb DescribeHealthStatus` |

### Certificate Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Upload server cert | UploadServerCertificate | `UploadServerCertificate` | `aliyun slb UploadServerCertificate` |
| Upload CA cert | UploadCACertificate | `UploadCACertificate` | `aliyun slb UploadCACertificate` |
| Describe server certs | DescribeServerCertificates | `DescribeServerCertificates` | `aliyun slb DescribeServerCertificates` |
| Describe CA certs | DescribeCACertificates | `DescribeCACertificates` | `aliyun slb DescribeCACertificates` |
| Delete server cert | DeleteServerCertificate | `DeleteServerCertificate` | `aliyun slb DeleteServerCertificate` |
| Delete CA cert | DeleteCACertificate | `DeleteCACertificate` | `aliyun slb DeleteCACertificate` |
| Set cert name | SetServerCertificateName | `SetServerCertificateName` | `aliyun slb SetServerCertificateName` |
| Set CA cert name | SetCACertificateName | `SetCACertificateName` | `aliyun slb SetCACertificateName` |

### ACL Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create ACL | CreateAccessControlList | `CreateAccessControlList` | `aliyun slb CreateAccessControlList` |
| Describe ACLs | DescribeAccessControlLists | `DescribeAccessControlLists` | `aliyun slb DescribeAccessControlLists` |
| Describe ACL attribute | DescribeAccessControlListAttribute | `DescribeAccessControlListAttribute` | `aliyun slb DescribeAccessControlListAttribute` |
| Add ACL entries | AddAccessControlListEntry | `AddAccessControlListEntry` | `aliyun slb AddAccessControlListEntry` |
| Remove ACL entries | RemoveAccessControlListEntry | `RemoveAccessControlListEntry` | `aliyun slb RemoveAccessControlListEntry` |
| Set ACL attribute | SetAccessControlListAttribute | `SetAccessControlListAttribute` | `aliyun slb SetAccessControlListAttribute` |
| Delete ACL | DeleteAccessControlList | `DeleteAccessControlList` | `aliyun slb DeleteAccessControlList` |

### Forwarding Rule Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create rules | CreateRules | `CreateRules` | `aliyun slb CreateRules` |
| Describe rules | DescribeRules | `DescribeRules` | `aliyun slb DescribeRules` |
| Describe rule attribute | DescribeRuleAttribute | `DescribeRuleAttribute` | `aliyun slb DescribeRuleAttribute` |
| Set rule | SetRule | `SetRule` | `aliyun slb SetRule` |
| Delete rules | DeleteRules | `DeleteRules` | `aliyun slb DeleteRules` |

### Region/Zone Operations

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Describe regions | DescribeRegions | `DescribeRegions` | `aliyun slb DescribeRegions` |
| Describe zones | DescribeZones | `DescribeZones` | `aliyun slb DescribeZones` |
| Describe available resource | DescribeAvailableResource | `DescribeAvailableResource` | `aliyun slb DescribeAvailableResource` |

## SDK Package (Go)

```bash
# Product-specific SDK for SLB
go get github.com/alibabacloud-go/slb-20140515/v2/client
```

## Request / Response Notes

- **Required fields** for CreateLoadBalancer: `RegionId`
- **Pagination**: DescribeLoadBalancers uses `PageNumber` and `PageSize` (max 100)
- **ClientToken**: Recommended for all write operations to ensure idempotency
- **BackendServers format**: JSON array string, e.g., `[{"ServerId":"i-xxx","Weight":"100","Port":"80"}]`
- **RuleList format**: JSON array string, e.g., `[{"RuleName":"r1","Domain":"example.com","Url":"/api/*"}]`
- **AclEntrys format**: JSON array string, e.g., `[{"entry":"10.0.0.0/8","comment":"office"}]`
