# Troubleshooting — ALB

> Version: 1.0.0 | Last Updated: 2026-06-07

## Common API Error Codes

| Code | Meaning | Agent Action |
|------|---------|--------------|
| InvalidParameter | Parameter validation failed | FIX — align with OpenAPI spec |
| OperationDenied | Operation not allowed in current state | FIX — verify resource status via Get/List |
| QuotaExceeded.LoadBalancer | ALB instance quota exceeded | HALT — request increase or delete unused |
| QuotaExceeded.Listener | Listener quota exceeded | HALT — delete unused or request increase |
| QuotaExceeded.ServerGroup | Server group quota exceeded | HALT — request increase |
| InsufficientBalance | Account balance insufficient | HALT — recharge account |
| Forbidden.ResourceNotFound | Resource does not exist | FIX — verify ID with List/Get |
| Forbidden.ResourceInUse | Resource in use by another operation | RETRY — wait 5s-30s, check ListAsynJobs |
| DeleteProtectionEnabled | Deletion protection enabled | HALT — user must disable first |
| IncorrectStatus.Listener | Listener in wrong state | FIX — verify listener status (active/inactive) |
| IncorrectStatus.LoadBalancer | ALB in wrong state | FIX — verify ALB status via GetLoadBalancerAttribute |
| Throttling | API rate limit exceeded | 3× retry exponential backoff (2s,4s,8s) |
| InternalError | Server-side error | 3× retry; then HALT with RequestId |
| Zone.NotEnoughResources | No available resources in zone | FIX — select different zone |
| CertNotFound | Certificate not found | FIX — verify certificate ID exists |
| InvalidSecurityPolicy.NotFound | Security policy not found | FIX — use ListSecurityPolicies |
| AclConflict | ACL type conflict on listener | FIX — only one Black + one White per listener |
| ServerGroup.StillReferenced | Server group still referenced | HALT — remove all references before deletion |
| Acl.StillReferenced | ACL still associated with listeners | HALT — dissociate from all listeners first |

## Diagnostic Order

1. **Identify the resource:** Use `ListLoadBalancers` or `GetLoadBalancerAttribute` to confirm the target ALB exists and its status.
2. **Check listener state:** `GetListenerAttribute` to verify listener status (Active/Inactive).
3. **Verify server group health:** `ListServerGroupServers` with `--output` to check server status and health.
4. **Check ACL associations:** `ListAclRelations` to see which listeners are associated with an ACL.
5. **Review async jobs:** `ListAsynJobs` for pending/completed async operations.
6. **Verify network:** Confirm VPC, VSwitch, and security group allow required traffic.
7. **Check quotas:** Compare current resource count against limits in `core-concepts.md`.

## Common Issues

### Health Check Failures

| Symptom | Possible Cause | Resolution |
|---------|---------------|---|
| Backend servers show unhealthy | Incorrect health check path | Verify `HealthCheckPath` returns 2xx/3xx |
| Intermittent health check flapping | Health check timeout < server response time | Increase `HealthCheckTimeoutSeconds` or `UnhealthyThreshold` |
| All servers unhealthy | Security group blocks health check traffic | Add inbound rule allowing ALB's health check IPs |
| Health check shows wrong status | Incorrect HTTP code range | Check `HealthCheckHttpCode` parameter |

### Connection Issues

| Symptom | Possible Cause | Resolution |
|---------|---------------|---|
| Clients get 503 | No healthy backend servers | Check server health and add servers if empty |
| Clients get 504 | Backend server timeout | Increase backend timeout config |
| SSL handshake failures | TLS version mismatch | Verify SecurityPolicy TLS version matches client capability |
| SNI not working | Additional cert not properly associated | Verify SNI domain name matches listener cert list |

### Deletion Failures

| Symptom | Possible Cause | Resolution |
|---------|---------------|---|
| Cannot delete ALB | Delete protection enabled | Use `DisableDeletionProtection` first |
| Cannot delete server group | Referenced by listener/rule | Remove all forwarding rules referencing this group |
| Cannot delete ACL | Associated with listener(s) | Use `DissociateAclsFromListener` first |
| Cannot delete security policy | Referenced by listener | Update listener to use a different security policy |

### Quota Issues

| Symptom | Possible Cause | Resolution |
|---------|---------------|---|
| Cannot create ALB | Region quota reached | Delete unused ALBs or request quota increase |
| Cannot add listener | Per-ALB listener limit reached | Delete unused listeners or request quota increase |
| Cannot add forwarding rule | Per-listener rule limit reached | Consolidate rules or switch to Standard edition |

## Product-Specific Error Patterns

### ALB-001: ServerGroup Empty After Health Check Failure

- **Trigger:** All backend servers marked unhealthy
- **Diagnosis:** Check `ListServerGroupServers` for server status; verify health check configuration
- **Recovery:** Fix health check settings (path, port, protocol) or backend server health
- **Prevention:** Use `ApplyHealthCheckTemplateToServerGroup` with validated template

### ALB-002: Listener Stuck in Inactive State

- **Trigger:** `StartListener` returns success but listener remains Inactive
- **Diagnosis:** Check ALB status (`GetLoadBalancerAttribute`); verify backend servers exist and are healthy
- **Recovery:** Ensure at least one server group with healthy servers is associated via default action
- **Prevention:** Verify server group health before starting listener

### ALB-003: Zone Migration Failure

- **Trigger:** `UpdateLoadBalancerZones` returns error or job fails
- **Diagnosis:** Check new VSwitch exists, has available IPs, and is in the same VPC
- **Recovery:** Verify the target VSwitch's CIDR has sufficient free IPs; retry with valid zone-VSwitch mapping
- **Prevention:** Always verify VSwitch available IP count before zone change

### ALB-004: AScript Parse Error

- **Trigger:** `CreateAScripts` fails with syntax error
- **Diagnosis:** Script content has syntax errors
- **Recovery:** Validate AScript syntax before deployment; test with simplified script first
- **Prevention:** Use small incremental script changes

### ALB-005: Edition Downgrade Not Allowed

- **Trigger:** `UpdateLoadBalancerEdition` to lower edition fails
- **Diagnosis:** ALB only supports edition upgrades (Basic→Standard→StandardWithWaf), not downgrades
- **Recovery:** Create a new ALB instance with the desired edition and migrate configuration
- **Prevention:** Choose appropriate edition at creation time