# Troubleshooting Alibaba Cloud ECS

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `InvalidParameter` / 400 | Request failed validation | Align body with OpenAPI; check required fields |
| `InvalidInstanceId.NotFound` / 404 | Instance does not exist | Verify InstanceId; check region |
| `InvalidDiskId.NotFound` / 404 | Disk does not exist | Verify DiskId; check region |
| `InvalidSecurityGroupId.NotFound` / 404 | Security group does not exist | Verify SecurityGroupId |
| `Forbidden.RAM` / 403 | Insufficient RAM permissions | User adds RAM policy for ECS operations |
| `InternalError` / 500 | Server-side error | Retry with backoff; then HALT |
| `Throttling` / 429 | Rate limit exceeded | Back off exponentially; respect Retry-After |
| `QuotaExceeded.Instance` / 403 | Instance quota exceeded | HALT; user raises quota or deletes unused instances |
| `QuotaExceeded.Disk` / 403 | Disk quota exceeded | HALT; user raises quota or deletes unused disks |
| `InsufficientBalance` / 400 | Account balance insufficient | HALT; user adds funds |
| `IncorrectInstanceStatus` / 403 | Instance not in expected state | Check current status; wait or change state first |
| `IncorrectDiskStatus` / 403 | Disk not in expected state | Check current status; detach/attach as needed |
| `InstanceLockedForSecurity` / 403 | Instance locked for security reasons | Contact Alibaba Cloud support |
| `OperationDenied` / 403 | Operation not allowed in current state | Check instance/disk status and try again |
| `InvalidAccessKeyId.NotFound` / 404 | Access key does not exist | Verify `ALIBABA_CLOUD_ACCESS_KEY_ID` is correct |
| `SignatureDoesNotMatch` / 400 | Access key secret incorrect | Verify `ALIBABA_CLOUD_ACCESS_KEY_SECRET` is correct |
| `InvalidParameter.Permissions` / 400 | Permissions array format invalid | Use JSON array format for `--Permissions` |

## Diagnostic Order

1. **Verify resource exists**: Describe by ID.
2. **Check status**: Ensure resource is in expected state for the operation.
3. **Check region/zone consistency**: Instance, disk, and VSwitch must be in the same zone.
4. **Verify CLI metadata coverage**: `aliyun help ecs`
5. **Check credentials**: `aliyun ecs DescribeRegions`
6. **Check quotas**: `aliyun ecs DescribeAccountAttributes`

## Instance Status Issues

### Instance stuck in "Starting" or "Stopping"
- Wait and retry; some operations take time
- Check if instance is locked: `aliyun ecs DescribeInstances --InstanceIds '["..."]'`
- If stuck > 10 minutes, contact support with RequestId

### Cannot delete instance
- Instance must be in `Stopped` state
- Use `aliyun ecs StopInstance` first, or use `--Force true` with `DeleteInstance`
- Check if instance has associated resources (disks, ENIs) that prevent deletion

## Disk Issues

### Cannot attach disk
- Disk must be in `Available` state
- Disk and instance must be in the same zone
- Check instance disk attachment limit

### Cannot detach disk
- Disk must be in `In_use` state
- Ensure disk is not mounted in the OS
- System disk cannot be detached

## Security Group Issues

### Cannot connect to instance
- Verify security group rules allow the required ports
- Check if source CIDR is correct
- Verify instance has public IP or is accessed via VPN/VPC

### Rule conflicts
- Security group rules are evaluated by priority (lower number = higher priority)
- `drop` rules override `accept` rules at same priority

## Network Issues

### No public IP
- Check `InternetMaxBandwidthOut` > 0
- Verify if instance is in VPC with NAT Gateway
- Check EIP association

### Cannot access instance via SSH/RDP
- Verify security group allows port 22 (SSH) or 3389 (RDP)
- Check if instance is Running
- Verify correct username/password or key pair

## Performance Issues

### High CPU / Memory
- Use CloudMonitor to check metrics
- Consider upgrading instance type
- Check for runaway processes

### Disk I/O issues
- Consider upgrading to `cloud_essd` category
- Check if disk is reaching IOPS/bandwidth limits
