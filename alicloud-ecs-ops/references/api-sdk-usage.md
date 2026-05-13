# API & SDK — Alibaba Cloud ECS

## OpenAPI

- **Service**: ECS
- **API Version**: 2014-05-26
- **Base Endpoint**: `ecs.aliyuncs.com` (regional endpoints also available)
- **Official Docs**: https://www.alibabacloud.com/help/en/ecs
- **OpenAPI Explorer**: https://api.aliyun.com/

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Create instance | `CreateInstance` | `CreateInstance()` | `aliyun ecs CreateInstance` |
| Describe instances | `DescribeInstances` | `DescribeInstances()` | `aliyun ecs DescribeInstances` |
| Start instance | `StartInstance` | `StartInstance()` | `aliyun ecs StartInstance` |
| Stop instance | `StopInstance` | `StopInstance()` | `aliyun ecs StopInstance` |
| Reboot instance | `RebootInstance` | `RebootInstance()` | `aliyun ecs RebootInstance` |
| Delete instance | `DeleteInstance` | `DeleteInstance()` | `aliyun ecs DeleteInstance` |
| Create disk | `CreateDisk` | `CreateDisk()` | `aliyun ecs CreateDisk` |
| Describe disks | `DescribeDisks` | `DescribeDisks()` | `aliyun ecs DescribeDisks` |
| Attach disk | `AttachDisk` | `AttachDisk()` | `aliyun ecs AttachDisk` |
| Detach disk | `DetachDisk` | `DetachDisk()` | `aliyun ecs DetachDisk` |
| Delete disk | `DeleteDisk` | `DeleteDisk()` | `aliyun ecs DeleteDisk` |
| Create snapshot | `CreateSnapshot` | `CreateSnapshot()` | `aliyun ecs CreateSnapshot` |
| Describe snapshots | `DescribeSnapshots` | `DescribeSnapshots()` | `aliyun ecs DescribeSnapshots` |
| Delete snapshot | `DeleteSnapshot` | `DeleteSnapshot()` | `aliyun ecs DeleteSnapshot` |
| Create security group | `CreateSecurityGroup` | `CreateSecurityGroup()` | `aliyun ecs CreateSecurityGroup` |
| Describe security groups | `DescribeSecurityGroups` | `DescribeSecurityGroups()` | `aliyun ecs DescribeSecurityGroups` |
| Authorize security group | `AuthorizeSecurityGroup` | `AuthorizeSecurityGroup()` | `aliyun ecs AuthorizeSecurityGroup` |
| Revoke security group | `RevokeSecurityGroup` | `RevokeSecurityGroup()` | `aliyun ecs RevokeSecurityGroup` |
| Describe regions | `DescribeRegions` | `DescribeRegions()` | `aliyun ecs DescribeRegions` |
| Describe zones | `DescribeZones` | `DescribeZones()` | `aliyun ecs DescribeZones` |
| Describe instance types | `DescribeInstanceTypes` | `DescribeInstanceTypes()` | `aliyun ecs DescribeInstanceTypes` |
| Run instances (batch) | `RunInstances` | `RunInstances()` | `aliyun ecs RunInstances` |
| Modify instance attribute | `ModifyInstanceAttribute` | `ModifyInstanceAttribute()` | `aliyun ecs ModifyInstanceAttribute` |
| Describe images | `DescribeImages` | `DescribeImages()` | `aliyun ecs DescribeImages` |

## SDK Package

```bash
go get github.com/alibabacloud-go/ecs-20140526/v4/client
```

## Request / Response Notes

### CreateInstance
- **Required fields**: `RegionId`, `ImageId`, `InstanceType`, `SecurityGroupId`
- **Optional but common**: `ZoneId`, `VSwitchId`, `InstanceName`, `Password`, `KeyPairName`
- **Response**: `InstanceId`

### DescribeInstances
- **Pagination**: `PageNumber`, `PageSize` (default 10, max 100)
- **Filters**: `InstanceIds` (JSON array), `Status`, `InstanceName`
- **Response**: `Instances.Instance[]` array

### StartInstance / StopInstance / RebootInstance
- **Required**: `InstanceId`
- **Stop options**: `ForceStop` (boolean), `StoppedMode` (`StopCharging` or `KeepCharging`)

### CreateDisk
- **Required**: `RegionId`, `Size` (GB)
- **Optional**: `ZoneId`, `DiskName`, `DiskCategory`, `Encrypted`
- **Note**: If `InstanceId` is specified, disk is created and attached in one step
- **Response**: `DiskId`

### AttachDisk
- **Required**: `InstanceId`, `DiskId`
- **Optional**: `Device` (e.g., `/dev/xvdb`)

### CreateSnapshot
- **Required**: `DiskId`
- **Optional**: `SnapshotName`, `Description`
- **Response**: `SnapshotId`

### AuthorizeSecurityGroup
- **Required**: `SecurityGroupId`, `RegionId`
- **Rule params** (use `Permissions.N.*` array format; old flat params are deprecated):
  - `IpProtocol`: `tcp`, `udp`, `icmp`, `gre`, `all`
  - `PortRange`: e.g., `22/22`, `80/80`, `1/65535`
  - `SourceCidrIp`: e.g., `0.0.0.0/0`
  - `Policy`: `accept` or `drop`
  - `Priority`: `1` to `100` (lower = higher priority)

### RunInstances (Batch Create)
- **Required**: `RegionId`, `ImageId`, `InstanceType`, `SecurityGroupId`
- **Optional**: `Amount` (1-100, default 1), `ZoneId`, `VSwitchId`, `InstanceName`
- **Response**: `InstanceIdSets.InstanceIdSet[]`

### ModifyInstanceAttribute
- **Required**: `InstanceId`
- **Modifiable fields**: `InstanceName`, `Password`, `Description`, `UserData`
- **Note**: `Password` change requires instance to be `Stopped`

### DescribeImages
- **Required**: `RegionId`
- **Filters**: `ImageOwnerAlias` (`system`, `self`, `others`, `marketplace`), `OSType` (`Linux`, `Windows`), `ImageName`
- **Response**: `Images.Image[]`

## Pagination Pattern

Most list/describe APIs support pagination:

```bash
aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --PageNumber 1 \
  --PageSize 50
```

```go
req := &ecs.DescribeInstancesRequest{
    RegionId:   tea.String("cn-hangzhou"),
    PageNumber: tea.Int32(1),
    PageSize:   tea.Int32(50),
}
```
