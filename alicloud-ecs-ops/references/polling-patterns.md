# Polling Patterns — ECS

## Generic Polling Template

### Using `--waiter` (if supported by CLI version)

```bash
aliyun ecs {{describe_command}} \
  --RegionId "{{user.region}}" \
  {{extra_params}} \
  --waiter expr='{{jq_path}}' to={{target_state}} timeout={{timeout}} interval={{interval}}
```

### Manual polling loop (universal compatibility)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATE=$(aliyun ecs {{describe_command}} \
    --RegionId "{{user.region}}" \
    {{extra_params}} | jq -r '{{jq_path}}')
  [ "$STATE" = "{{target_state}}" ] && break
  sleep {{interval}}
done
```

### Polling for resource absence (e.g. DeleteInstance)

```bash
for i in $(seq 1 {{max_retries}}); do
  COUNT=$(aliyun ecs {{describe_command}} \
    --RegionId "{{user.region}}" \
    {{extra_params}} \
    --output cols=TotalCount rows=TotalCount)
  [ "$COUNT" = "0" ] && break
  sleep {{interval}}
done
```

### Polling for terminal status (e.g. RunCommand, SendFile)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun ecs {{describe_command}} \
    --RegionId "{{user.region}}" \
    {{extra_params}} \
    --output cols={{status_field}} rows={{status_jq_path}})
  case "$STATUS" in
    {{success_status}}) echo "Operation completed successfully"; break ;;
    {{failure_statuses}}) echo "Operation failed with status: $STATUS"; break ;;
  esac
  sleep {{interval}}
done
```

## Per-Operation Polling Parameters

### Instance Lifecycle

| Operation | Describe Command | Extra Params | JQ Path | Target State | Interval | Max Retries |
|-----------|-----------------|-------------|---------|--------------|----------|-------------|
| CreateInstance | DescribeInstances | `--InstanceIds '["{{output.instance_id}}"]'` | `$.Instances.Instance[0].Status` | Running | 10s | 60 |
| StartInstance | DescribeInstances | `--InstanceIds '["{{user.instance_id}}"]'` | `$.Instances.Instance[0].Status` | Running | 10s | 30 |
| StopInstance | DescribeInstances | `--InstanceIds '["{{user.instance_id}}"]'` | `$.Instances.Instance[0].Status` | Stopped | 10s | 30 |
| RebootInstance | DescribeInstances | `--InstanceIds '["{{user.instance_id}}"]'` | `$.Instances.Instance[0].Status` | Running | 10s | 30 |
| DeleteInstance | DescribeInstances | `--InstanceIds '["{{user.instance_id}}"]'` | (absent — check TotalCount=0) | absent | 10s | 30 |
| RunInstances | DescribeInstances | `--InstanceIds '["{{output.instance_ids}}"]'` | `$.Instances.Instance[0].Status` | Running | 10s | 60 |
| ReplaceSystemDisk | DescribeInstances | `--InstanceIds '["{{user.instance_id}}"]'` | `$.Instances.Instance[0].Status` | Stopped | 10s | 60 |

### Disk Operations

| Operation | Describe Command | Extra Params | JQ Path | Target State | Interval | Max Retries |
|-----------|-----------------|-------------|---------|--------------|----------|-------------|
| CreateDisk | DescribeDisks | `--DiskIds '["{{output.disk_id}}"]'` | `$.Disks.Disk[0].Status` | Available | 5s | 24 |
| AttachDisk | DescribeDisks | `--DiskIds '["{{user.disk_id}}"]'` | `$.Disks.Disk[0].Status` | In_use | 5s | 24 |
| DetachDisk | DescribeDisks | `--DiskIds '["{{user.disk_id}}"]'` | `$.Disks.Disk[0].Status` | Available | 5s | 24 |

### Snapshot Operations

| Operation | Describe Command | Extra Params | JQ Path | Target State | Interval | Max Retries |
|-----------|-----------------|-------------|---------|--------------|----------|-------------|
| CreateSnapshot | DescribeSnapshots | `--SnapshotIds '["{{output.snapshot_id}}"]'` | `$.Snapshots.Snapshot[0].Status` | accomplished | 10s | 60 |

### Security Group Operations

| Operation | Describe Command | Extra Params | JQ Path | Target State | Interval | Max Retries |
|-----------|-----------------|-------------|---------|--------------|----------|-------------|
| CreateSecurityGroup | DescribeSecurityGroups | `--SecurityGroupIds '["{{output.security_group_id}}"]'` | `$.SecurityGroups.SecurityGroup[0].SecurityGroupId` | (exists) | 5s | 12 |

### Cloud Assistant Operations

| Operation | Describe Command | Extra Params | Status Field | Status JQ Path | Success Status | Failure Statuses | Interval | Max Retries |
|-----------|-----------------|-------------|-------------|----------------|----------------|-----------------|----------|-------------|
| RunCommand | DescribeInvocationResults | `--InvokeId "{{output.invoke_id}}" --InstanceId "{{user.instance_id}}"` | InvocationStatus | `$.Invocation.InvocationResults.InvocationResult[0].InvocationStatus` | Success | Failed,Timeout,Cancelled | 5s | 60 |
| SendFile | DescribeSendFileResults | `--InvokeId "{{output.invoke_id}}" --InstanceId "{{user.instance_id}}"` | FileStatus | `$.SendFileResults.SendFileResult[0].FileStatus` | Success | Failed,PartialFailed | 5s | 60 |
