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

## Go SDK Examples

代码示例使用以下环境变量注入参数：`ALIBABA_CLOUD_REGION_ID`, `INSTANCE_ID`, `DISK_ID`, `IMAGE_ID`, `SECURITY_GROUP_ID`, `VSWITCH_ID`, `ZONE_ID`, `INSTANCE_TYPE`, `INSTANCE_NAME`, `KEY_PAIR_NAME`, `SNAPSHOT_ID`, `VPC_ID` 等。

> 所有代码片段均假设已在文件顶部导入：
> ```go
> import (
>     "github.com/alibabacloud-go/tea/tea"
>     ecs "github.com/alibabacloud-go/ecs-20140526/v4/client"
> )
> ```

### CreateInstance

完整客户端初始化 + 创建实例 + 轮询至 Running 状态：

```go
package main

import (
	"fmt"
	"os"
	"time"

	openapi "github.com/alibabacloud-go/darabonba-openapi/v2/client"
	"github.com/alibabacloud-go/tea/tea"
	ecs "github.com/alibabacloud-go/ecs-20140526/v4/client"
)

func main() {
	config := &openapi.Config{
		AccessKeyId:     tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
		AccessKeySecret: tea.String(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
		RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	}

	c, err := ecs.NewClient(config)
	if err != nil {
		panic(err)
	}

	req := &ecs.CreateInstanceRequest{
		RegionId:              tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
		ZoneId:                tea.String(os.Getenv("ZONE_ID")),
		ImageId:               tea.String(os.Getenv("IMAGE_ID")),
		InstanceType:          tea.String(os.Getenv("INSTANCE_TYPE")),
		SecurityGroupId:       tea.String(os.Getenv("SECURITY_GROUP_ID")),
		VSwitchId:             tea.String(os.Getenv("VSWITCH_ID")),
		InstanceName:          tea.String(os.Getenv("INSTANCE_NAME")),
		InternetMaxBandwidthOut: tea.Int(1),
		KeyPairName:           tea.String(os.Getenv("KEY_PAIR_NAME")),
	}

	resp, err := c.CreateInstance(req)
	if err != nil {
		panic(err)
	}

	instanceId := tea.ToString(resp.Body.InstanceId)
	fmt.Printf("Created instance: %s\n", instanceId)

	// Poll until Running
	for i := 0; i < 60; i++ {
		descReq := &ecs.DescribeInstancesRequest{
			RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
			InstanceIds: tea.String(`["` + instanceId + `"]`),
		}
		descResp, err := c.DescribeInstances(descReq)
		if err != nil {
			panic(err)
		}
		instances := descResp.Body.Instances.Instance
		if len(instances) > 0 && tea.ToString(instances[0].Status) == "Running" {
			fmt.Println("Instance is Running")
			break
		}
		time.Sleep(5 * time.Second)
	}
}
```

**UserData Note:** 传递初始化脚本时，添加 `UserData` 字段并 base64 编码：
```go
import "encoding/base64"
userData := base64.StdEncoding.EncodeToString([]byte("#!/bin/bash\necho 'hello' > /tmp/setup.log"))
req.UserData = tea.String(userData)
```

### DescribeInstances

```go
req := &ecs.DescribeInstancesRequest{
	RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InstanceIds: tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
}
resp, err := c.DescribeInstances(req)
```

### RunInstances (Batch Create)

```go
req := &ecs.RunInstancesRequest{
	RegionId:              tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	ZoneId:                tea.String(os.Getenv("ZONE_ID")),
	ImageId:               tea.String(os.Getenv("IMAGE_ID")),
	InstanceType:          tea.String(os.Getenv("INSTANCE_TYPE")),
	SecurityGroupId:       tea.String(os.Getenv("SECURITY_GROUP_ID")),
	VSwitchId:             tea.String(os.Getenv("VSWITCH_ID")),
	InstanceName:          tea.String(os.Getenv("INSTANCE_NAME")),
	Amount:                tea.Int32(2),
	InternetMaxBandwidthOut: tea.Int(1),
	KeyPairName:           tea.String(os.Getenv("KEY_PAIR_NAME")),
}
resp, err := c.RunInstances(req)
// Parse InstanceIdSets.InstanceIdSet[] from response
```

### ModifyInstanceAttribute

```go
req := &ecs.ModifyInstanceAttributeRequest{
	InstanceId:   tea.String(os.Getenv("INSTANCE_ID")),
	InstanceName: tea.String(os.Getenv("NEW_INSTANCE_NAME")),
}
resp, err := c.ModifyInstanceAttribute(req)
```

### DescribeImages

```go
req := &ecs.DescribeImagesRequest{
	RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	ImageOwnerAlias: tea.String("system"),
	OSType:          tea.String("Linux"),
}
resp, err := c.DescribeImages(req)
```

### StartInstance

```go
req := &ecs.StartInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.StartInstance(req)
```

### StopInstance

```go
req := &ecs.StopInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	ForceStop:  tea.Bool(false),
}
resp, err := c.StopInstance(req)
```

### RebootInstance

```go
req := &ecs.RebootInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	ForceStop:  tea.Bool(false),
}
resp, err := c.RebootInstance(req)
```

### DeleteInstance

```go
req := &ecs.DeleteInstanceRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	Force:      tea.Bool(false),
}
resp, err := c.DeleteInstance(req)
```

### CreateDisk

```go
size, _ := strconv.Atoi(os.Getenv("DISK_SIZE"))
req := &ecs.CreateDiskRequest{
	RegionId:     tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	ZoneId:       tea.String(os.Getenv("ZONE_ID")),
	DiskName:     tea.String(os.Getenv("DISK_NAME")),
	Size:         tea.Int32(int32(size)),
	DiskCategory: tea.String(os.Getenv("DISK_CATEGORY")),
}
resp, err := c.CreateDisk(req)
```

**Disk Encryption:** 启用加密：
```go
req.Encrypted = tea.Bool(true)
req.KMSKeyId = tea.String("alias/acs/ecs")
```

### AttachDisk

```go
req := &ecs.AttachDiskRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	DiskId:     tea.String(os.Getenv("DISK_ID")),
}
resp, err := c.AttachDisk(req)
```

### DetachDisk

```go
req := &ecs.DetachDiskRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	DiskId:     tea.String(os.Getenv("DISK_ID")),
}
resp, err := c.DetachDisk(req)
```

### DeleteDisk

```go
req := &ecs.DeleteDiskRequest{
	DiskId: tea.String(os.Getenv("DISK_ID")),
}
resp, err := c.DeleteDisk(req)
```

### CreateSnapshot

```go
req := &ecs.CreateSnapshotRequest{
	DiskId:       tea.String(os.Getenv("DISK_ID")),
	SnapshotName: tea.String(os.Getenv("SNAPSHOT_NAME")),
}
resp, err := c.CreateSnapshot(req)
```

### DeleteSnapshot

```go
req := &ecs.DeleteSnapshotRequest{
	SnapshotId: tea.String(os.Getenv("SNAPSHOT_ID")),
}
resp, err := c.DeleteSnapshot(req)
```

### CreateSecurityGroup

```go
req := &ecs.CreateSecurityGroupRequest{
	RegionId:          tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	SecurityGroupName: tea.String(os.Getenv("SECURITY_GROUP_NAME")),
	VpcId:             tea.String(os.Getenv("VPC_ID")),
}
resp, err := c.CreateSecurityGroup(req)
```

### AuthorizeSecurityGroup

```go
req := &ecs.AuthorizeSecurityGroupRequest{
	SecurityGroupId: tea.String(os.Getenv("SECURITY_GROUP_ID")),
	RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	Permissions: []*ecs.AuthorizeSecurityGroupRequestPermissions{
		{
			IpProtocol:   tea.String("tcp"),
			PortRange:    tea.String("22/22"),
			SourceCidrIp: tea.String(os.Getenv("SOURCE_CIDR_IP")),
			Policy:       tea.String("accept"),
			Priority:     tea.String("1"),
			Description:  tea.String("SSH access from admin IP"),
		},
	},
}
resp, err := c.AuthorizeSecurityGroup(req)
```

### RevokeSecurityGroup

```go
req := &ecs.RevokeSecurityGroupRequest{
	SecurityGroupId:       tea.String(os.Getenv("SECURITY_GROUP_ID")),
	RegionId:              tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	SecurityGroupRuleId: []*string{
		tea.String(os.Getenv("RULE_ID")),
	},
}
resp, err := c.RevokeSecurityGroup(req)
```

### DescribeSecurityGroupAttribute

```go
req := &ecs.DescribeSecurityGroupAttributeRequest{
	SecurityGroupId: tea.String(os.Getenv("SECURITY_GROUP_ID")),
	RegionId:        tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
}
resp, err := c.DescribeSecurityGroupAttribute(req)
```

### AddTags

```go
req := &ecs.AddTagsRequest{
	ResourceType: tea.String("instance"),
	ResourceId:   tea.String(os.Getenv("INSTANCE_ID")),
	Tags: []*ecs.AddTagsRequestTags{
		{Key: tea.String("Environment"), Value: tea.String("Production")},
		{Key: tea.String("Owner"), Value: tea.String("DevOps")},
	},
}
resp, err := c.AddTags(req)
```

### DescribeTags

```go
req := &ecs.DescribeTagsRequest{
	RegionId:     tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	ResourceType: tea.String("instance"),
	ResourceId:   tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeTags(req)
```

### RemoveTags

```go
req := &ecs.RemoveTagsRequest{
	ResourceType: tea.String("instance"),
	ResourceId:   tea.String(os.Getenv("INSTANCE_ID")),
	TagKey:       []*string{tea.String("Environment"), tea.String("Owner")},
}
resp, err := c.RemoveTags(req)
```

### ResizeDisk

```go
newSize, _ := strconv.Atoi(os.Getenv("NEW_SIZE"))
req := &ecs.ResizeDiskRequest{
	DiskId:  tea.String(os.Getenv("DISK_ID")),
	NewSize: tea.Int32(int32(newSize)),
}
resp, err := c.ResizeDisk(req)
```

### ReplaceSystemDisk

```go
req := &ecs.ReplaceSystemDiskRequest{
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
	ImageId:    tea.String(os.Getenv("IMAGE_ID")),
}
resp, err := c.ReplaceSystemDisk(req)
```

### RunCommand (Cloud Assistant)

```go
req := &ecs.RunCommandRequest{
	RegionId:       tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InstanceIds:    tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
	CommandContent: tea.String(os.Getenv("COMMAND_CONTENT")),
	Type:           tea.String(os.Getenv("COMMAND_TYPE")),
	Name:           tea.String(os.Getenv("COMMAND_NAME")),
	Timeout:        tea.Int64(60),
}
resp, err := c.RunCommand(req)
```

### InvokeCommand

```go
req := &ecs.InvokeCommandRequest{
	RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	CommandId:   tea.String(os.Getenv("COMMAND_ID")),
	InstanceIds: tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
	Parameters:  tea.String(`{"var1":"value1"}`),
}
resp, err := c.InvokeCommand(req)
```

### DescribeInvocationResults

```go
req := &ecs.DescribeInvocationResultsRequest{
	RegionId:   tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InvokeId:   tea.String(os.Getenv("INVOKE_ID")),
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeInvocationResults(req)
```

### StopInvocation

```go
req := &ecs.StopInvocationRequest{
	RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InvokeId:    tea.String(os.Getenv("INVOKE_ID")),
	InstanceIds: tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
}
resp, err := c.StopInvocation(req)
```

### SendFile

```go
import "encoding/base64"
import "os"

fileContent, err := os.ReadFile(os.Getenv("LOCAL_FILE"))
if err != nil {
	panic(err)
}
encodedContent := base64.StdEncoding.EncodeToString(fileContent)

req := &ecs.SendFileRequest{
	RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InstanceIds: tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
	Name:        tea.String(os.Getenv("FILE_NAME")),
	Description: tea.String(os.Getenv("FILE_DESCRIPTION")),
	TargetDir:   tea.String(os.Getenv("TARGET_DIR")),
	FileOwner:   tea.String(os.Getenv("FILE_OWNER")),
	FileGroup:   tea.String(os.Getenv("FILE_GROUP")),
	FileMode:    tea.String(os.Getenv("FILE_MODE")),
	Content:     tea.String(encodedContent),
	Overwrite:   tea.Bool(true),
}
resp, err := c.SendFile(req)
```

### DescribeSendFileResults

```go
req := &ecs.DescribeSendFileResultsRequest{
	RegionId:   tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InvokeId:   tea.String(os.Getenv("INVOKE_ID")),
	InstanceId: tea.String(os.Getenv("INSTANCE_ID")),
}
resp, err := c.DescribeSendFileResults(req)
```

### DescribeCloudAssistantStatus

```go
req := &ecs.DescribeCloudAssistantStatusRequest{
	RegionId:    tea.String(os.Getenv("ALIBABA_CLOUD_REGION_ID")),
	InstanceIds: tea.String(`["` + os.Getenv("INSTANCE_ID") + `"]`),
}
resp, err := c.DescribeCloudAssistantStatus(req)
```
