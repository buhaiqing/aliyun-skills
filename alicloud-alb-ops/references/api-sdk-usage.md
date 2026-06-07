# API & SDK Usage — ALB

> Version: 1.0.0 | Last Updated: 2026-06-07

## OpenAPI

- **Service Endpoint:** `alb.aliyuncs.com`
- **API Version:** 2020-06-16
- Go SDK: `github.com/alibabacloud-go/alb-20200616/v2/client`

> JIT Go SDK client template & JIT workflow in [`integration.md`](integration.md).

## SDK Operations Map

| Goal | API operationId | Notes |
|------|-----------------|-------|
| **ALB Instance** |
| Create | `CreateLoadBalancer` | Async-polls via ListAsynJobs |
| List | `ListLoadBalancers` | Pagination: MaxResults + NextToken |
| Get | `GetLoadBalancerAttribute` | Full details including zones |
| Update | `UpdateLoadBalancerAttribute` | Name, modification protection |
| Delete | `DeleteLoadBalancer` | **Destructive** — requires safety gate |
| Edition | `UpdateLoadBalancerEdition` | Upgrade only |
| Zones | `UpdateLoadBalancerZones` | Modify zone mappings |
| Address type | `UpdateLoadBalancerAddressTypeConfig` | Intranet ↔ Internet |
| Deletion protection | `EnableDeletionProtection` / `DisableDeletionProtection` | |
| Access log | `EnableLoadBalancerAccessLog` / `DisableLoadBalancerAccessLog` | |
| **Listener** |
| Create | `CreateListener` | HTTP/HTTPS/QUIC |
| Get / List | `GetListenerAttribute` / `ListListeners` | |
| Update | `UpdateListenerAttribute` | Actions, certs, security policy |
| Log config | `UpdateListenerLogConfig` | |
| Start / Stop | `StartListener` / `StopListener` | |
| Delete | `DeleteListener` | **Destructive** |
| **Server Group** |
| Create / Get / List | `CreateServerGroup` / `GetServerGroupAttribute` / `ListServerGroups` | |
| Update | `UpdateServerGroupAttribute` | Scheduler, health check, persistence |
| Add / Remove / Replace servers | `AddServersToServerGroup` / `RemoveServersFromServerGroup` / `ReplaceServersInServerGroup` | Add is async |
| List servers | `ListServerGroupServers` | |
| Delete | `DeleteServerGroup` | **Destructive** — must not be referenced |
| **Forwarding Rule** |
| Create | `CreateRule` / `CreateRules` (batch) | |
| List / Update | `ListRules` / `UpdateRuleAttribute` / `UpdateRulesAttribute` | |
| Delete | `DeleteRule` / `DeleteRules` | **Destructive** |
| **ACL** |
| Create / Get / List | `CreateAcl` / `UpdateAclAttribute` / `ListAcls` / `ListAclEntries` | |
| Add / Remove entries | `AddEntriesToAcl` / `RemoveEntriesFromAcl` | |
| Associate / Dissociate | `AssociateAclsWithListener` / `DissociateAclsFromListener` | |
| Delete | `DeleteAcl` | **Destructive** |
| **Security Policy** |
| Create / List / Update / Delete | `CreateSecurityPolicy` / `ListSecurityPolicies` / `UpdateSecurityPolicyAttribute` / `DeleteSecurityPolicy` | |
| List system | `ListSystemSecurityPolicies` | |
| **Health Check Template** |
| Create / Get / List / Update | `CreateHealthCheckTemplate` / `GetHealthCheckTemplateAttribute` / `ListHealthCheckTemplates` / `UpdateHealthCheckTemplateAttribute` | |
| Apply | `ApplyHealthCheckTemplateToServerGroup` | |
| Delete | `DeleteHealthCheckTemplates` | |
| **Other** |
| Certificate | `ListListenerCertificates` / `AssociateAdditionalCertificatesWithListener` / `DissociateAdditionalCertificatesFromListener` | |
| AScript | `CreateAScripts` / `ListAScripts` / `UpdateAScripts` / `DeleteAScripts` | |
| Security Group | `LoadBalancerJoinSecurityGroup` / `LoadBalancerLeaveSecurityGroup` | |
| Tags | `TagResources` / `UnTagResources` / `ListTagKeys` / `ListTagValues` / `ListTagResources` | |
| Regions / Zones | `DescribeRegions` / `DescribeZones` | |
| Async jobs | `ListAsynJobs` | Poll async operations |

## Request / Response Notes

- **Async operations:** `CreateLoadBalancer`, `AddServersToServerGroup`, `UpdateLoadBalancerZones` return a JobId. Poll with `ListAsynJobs --JobId {{job_id}}`.
- **JSON arrays:** ALB uses JSON-encoded arrays for ZoneMappings, Servers, DefaultActions, Rules, AclEntries. Escape correctly in CLI.
- **Pagination:** Use `MaxResults` (default 100) + `NextToken` for cursor-based pagination.