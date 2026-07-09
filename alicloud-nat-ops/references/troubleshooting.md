# Troubleshooting NAT

> **Purpose:** Common NAT error codes, diagnostic steps, and solutions.

## Common Error Codes

| Error Code | HTTP | Meaning | Agent Action |
|------------|------|---------|--------------|
| `InvalidNatGatewayId.NotFound` | 404 | NAT Gateway does not exist | Verify NatGatewayId |
| `QuotaExceeded.NatGateway` | 400 | NAT Gateway quota reached | Delete unused or request increase |
| `QuotaExceeded.SnatEntry` | 400 | SNAT entry quota (200) reached | Delete unused entries |
| `DependencyViolation.SnatEntryExists` | 400 | SNAT entries exist | Delete SNAT entries before NAT deletion |
| `DependencyViolation.ForwardEntryExists` | 400 | DNAT entries exist | Delete DNAT entries before NAT deletion |
| `InvalidEipStatus.InUseByOtherNat` | 400 | EIP bound to different NAT | Unbind EIP or use different EIP |
| `MissingParameter.VSwitchId` | 400 | VSwitchId required for Enhanced NAT | Provide VSwitchId |
| `InvalidVSwitchId.NotFound` | 404 | VSwitch does not exist | Create VSwitch or correct ID |
| `InvalidSourceCIDR` | 400 | Source CIDR invalid | Fix CIDR format |
| `DuplicateSnatEntry` | 400 | SNAT entry already exists | Reuse existing entry or modify |
| `InsufficientBalance` | 400 | Account balance insufficient | HALT; recharge |
| `Forbidden.RAMUser` | 403 | RAM user lacks permissions | Add AliyunNATFullAccess policy |
| `Throttling` | 429 | Rate limit exceeded | Retry with exponential backoff |
| `InternalError` | 500 | Server internal error | Retry 3x; escalate with RequestId |

## Diagnostic Order

1. **Verify NAT Gateway exists:** `aliyun vpc DescribeNatGateways --NatGatewayId <id>`
2. **Check NAT status:** Must be `Available` for SNAT/DNAT operations
3. **Verify dependencies:** Delete SNAT entries → DNAT entries → unbund EIPs before NAT deletion
4. **Check EIP availability:** For SNAT/DNAT source, EIP must be allocated and not bound elsewhere
5. **Verify target ECS:** For DNAT, internal IP must be reachable from NAT Gateway vSwitch
6. **Check quotas:** NAT Gateway count, SNAT/DNAT entry count per NAT
7. **Check RAM permissions:** `AliyunNATFullAccess` or `AliyunVPCFullAccess`

## Common Scenarios

### SNAT — Private Instances Cannot Access Internet

Symptoms: ECS in VPC times out when accessing external URLs

1. Verify SNAT entry exists: `aliyun vpc DescribeSnatTableEntries`
2. Verify SNAT source CIDR/vSwitch matches the ECS CIDR
3. Verify EIP bound to SNAT is in `InUse` or `Available` state
4. Check ECS security group allows outbound traffic
5. Verify NAT Gateway status is `Available`
6. Check ECS route table — no conflicting routes
7. Verify SNAT EIP has sufficient bandwidth

### DNAT — External Traffic Not Reaching Internal Service

Symptoms: External connection to EIP:port times out

1. Verify DNAT entry exists: `aliyun vpc DescribeForwardTableEntries`
2. Verify protocol matches (TCP vs UDP)
3. Verify internal IP is correct and ECS has service listening on internal port
4. Check ECS security group allows inbound on internal port
5. Verify DNAT EIP is bound to the NAT Gateway
6. Test connectivity from within VPC to internal IP:port
7. Check ECS OS firewall (iptables/firewalld) rules

### NAT Gateway Deletion Blocked

Symptoms: DeleteNatGateway fails

1. List all SNAT entries: Delete each one
2. List all DNAT entries: Delete each one
3. List all FULLNAT entries: Delete each one
4. Check for bound EIPs: Unbind from NAT Gateway
5. Retry deletion

### "EIP already bound to another NAT"

Symptoms: Cannot add EIP to SNAT

1. Check which NAT the EIP is bound to: `aliyun vpc DescribeEipAddresses --AllocationId <id>`
2. Unbind EIP from old NAT: `aliyun vpc UnassociateEipAddress`
3. Re-bind to new NAT
