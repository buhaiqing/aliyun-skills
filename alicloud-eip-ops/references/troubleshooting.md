# Troubleshooting EIP

> **Purpose:** Common EIP error codes, diagnostic steps, and solutions.

## Common Error Codes

| Error Code | HTTP | Meaning | Agent Action |
|------------|------|---------|--------------|
| `InvalidAllocationId.NotFound` | 404 | EIP does not exist | Verify AllocationId; check region |
| `InvalidEipStatus` | 400 | EIP in wrong state for operation | Check current status; wait if transitioning |
| `QuotaExceeded.EipAddress` | 400 | EIP quota reached | Delete unused EIPs or request increase |
| `InsufficientBalance` | 400 | Account balance insufficient | HALT; user recharges |
| `InvalidBandwidth.ValueNotSupported` | 400 | Bandwidth out of range | Fix bandwidth: 1-200 (PayByTraffic), 1-500 (PayByBandwidth) |
| `InvalidInstance.Id.NotFound` | 404 | Target instance does not exist | Verify InstanceId and region match |
| `InvalidInstanceType.ValueNotSupported` | 400 | Invalid InstanceType | Use: EcsInstance, Nat, SLBInstance, HaVip, NetworkInterface, Ngw |
| `IncorrectEipStatus` | 400 | EIP status mismatch | Check current status before proceeding |
| `Throttling` | 429 | Rate limit exceeded | Retry with exponential backoff |
| `InternalError` | 500 | Alibaba Cloud internal error | Retry 3x; then escalate with RequestId |
| `Forbidden.RAMUser` | 403 | RAM user lacks permissions | Add `AliyunVPCFullAccess` policy |
| `OperationDenied` | 400 | Operation not permitted | Check resource lock or deletion protection |
| `DependencyViolation` | 400 | EIP has dependencies | Unbind all associations before release |

## Diagnostic Order

1. **Verify EIP exists:** `aliyun vpc DescribeEipAddresses --RegionId <region> --AllocationId <id>`
2. **Check EIP status:** Verify status is appropriate for the operation (Available for bind, InUse for unbind)
3. **Verify target instance:** Ensure the target resource exists and is in the same region
4. **Check InstanceType:** Ensure correct type for the target resource
5. **Verify quota:** `aliyun vpc DescribeEipAddresses` — count vs quota
6. **Check RAM permissions:** `AliyunVPCFullAccess` or equivalent
7. **Check balance:** Account must have sufficient balance

## Common Scenarios

### EIP Cannot Be Associated

Symptoms: `AssociateEipAddress` fails

1. Check EIP status — must be `Available`
2. Check for existing binding — EIP can only bind to one resource
3. Verify target instance exists in same region
4. Check instance type is supported for EIP binding

### EIP Public Access Failed After Binding

Symptoms: EIP bound but service unreachable

1. Verify EIP status is `InUse`
2. Check Security Group rules allow inbound traffic on target port
3. Check if ECS instance OS firewall is blocking
4. Verify bandwidth is sufficient (not throttled)
5. Check EIP billing — ensure account has balance

### Bandwidth Upgrade Failed

Symptoms: `ModifyEipAddressAttribute` with higher bandwidth fails

1. Check current billing mode compatibility
2. Verify new bandwidth is within allowed range
3. Check account balance for the upgrade charge
