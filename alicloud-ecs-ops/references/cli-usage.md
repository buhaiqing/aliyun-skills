# CLI — Alibaba Cloud ECS (`aliyun ecs`)

## Install and Config

- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **CRITICAL Credentials:** The `aliyun` CLI reads from env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR `~/.aliyun/config.json` (JSON format).
- For sandbox environments, set env vars directly (preferred) or use `--config-path`.

## Conventions (agent execution)

- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI — all commands are non-interactive by default
- Document **exact** JSON paths after verifying with a real invocation

## CLI vs API Coverage Gap

| Operation (API / SDK) | Available via `aliyun`? | Notes |
|------------------------|---------------------|-------|
| CreateInstance | yes | Full support |
| DescribeInstances | yes | Full support with pagination |
| StartInstance | yes | Full support |
| StopInstance | yes | Full support |
| RebootInstance | yes | Full support |
| DeleteInstance | yes | Full support |
| CreateDisk | yes | Full support |
| DescribeDisks | yes | Full support |
| AttachDisk | yes | Full support |
| DetachDisk | yes | Full support |
| DeleteDisk | yes | Full support |
| CreateSnapshot | yes | Full support |
| DescribeSnapshots | yes | Full support |
| DeleteSnapshot | yes | Full support |
| CreateSecurityGroup | yes | Full support |
| DescribeSecurityGroups | yes | Full support |
| AuthorizeSecurityGroup | yes | Full support |
| RevokeSecurityGroup | yes | Full support |
| DescribeRegions | yes | Full support |
| DescribeZones | yes | Full support |
| DescribeInstanceTypes | yes | Full support |
| RunInstances | yes | Full support |
| ModifyInstanceAttribute | yes | Full support |
| DescribeImages | yes | Full support |

> ECS is fully supported by the `aliyun` CLI. No SDK-only operations for basic CRUD.

## Command Map

### Instance Operations

```bash
# Create instance
aliyun ecs CreateInstance \
  --RegionId cn-hangzhou \
  --ZoneId cn-hangzhou-b \
  --ImageId ubuntu_22_04_x64_20G_alibase_20230516.vhd \
  --InstanceType ecs.g7.large \
  --SecurityGroupId sg-bp67acfmxazb4ph*** \
  --VSwitchId vsw-bp67acfmxazb4ph*** \
  --InstanceName my-ecs-instance \
  --InternetMaxBandwidthOut 1

# Describe all instances
aliyun ecs DescribeInstances --RegionId cn-hangzhou

# Describe specific instance
aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --InstanceIds '["i-bp67acfmxazb4ph***"]'

# Extract fields with JMESPath
aliyun ecs DescribeInstances --RegionId cn-hangzhou \
  --output cols=InstanceId,Status,InstanceName rows=Instances.Instance[].{InstanceId,Status,InstanceName}

# Start instance
aliyun ecs StartInstance --InstanceId i-bp67acfmxazb4ph***

# Stop instance
aliyun ecs StopInstance --InstanceId i-bp67acfmxazb4ph*** --ForceStop false

# Reboot instance
aliyun ecs RebootInstance --InstanceId i-bp67acfmxazb4ph*** --ForceStop false

# Delete instance (must be stopped first)
aliyun ecs DeleteInstance --InstanceId i-bp67acfmxazb4ph*** --Force false
```

### Disk Operations

```bash
# Create disk
aliyun ecs CreateDisk \
  --RegionId cn-hangzhou \
  --ZoneId cn-hangzhou-b \
  --Size 100 \
  --DiskCategory cloud_essd \
  --DiskName my-data-disk

# Describe disks
aliyun ecs DescribeDisks --RegionId cn-hangzhou

# Attach disk
aliyun ecs AttachDisk \
  --InstanceId i-bp67acfmxazb4ph*** \
  --DiskId d-bp67acfmxazb4ph***

# Detach disk
aliyun ecs DetachDisk \
  --InstanceId i-bp67acfmxazb4ph*** \
  --DiskId d-bp67acfmxazb4ph***

# Delete disk (must be detached first)
aliyun ecs DeleteDisk --DiskId d-bp67acfmxazb4ph***
```

### Batch Operations

```bash
# Run multiple instances at once
aliyun ecs RunInstances \
  --RegionId cn-hangzhou \
  --ZoneId cn-hangzhou-a \
  --ImageId centos_7_9_x64_20G_alibase_20230718.vhd \
  --InstanceType ecs.g7.large \
  --SecurityGroupId sg-bp67acfmxazb4ph*** \
  --VSwitchId vsw-bp67acfmxazb4ph*** \
  --Amount 3 \
  --InstanceNamePrefix web-server \
  --KeyPairName my-key-pair
```

### Instance Attribute Operations

```bash
# Rename instance
aliyun ecs ModifyInstanceAttribute \
  --InstanceId i-bp67acfmxazb4ph*** \
  --InstanceName new-name

# Reset password (instance must be Stopped)
aliyun ecs ModifyInstanceAttribute \
  --InstanceId i-bp67acfmxazb4ph*** \
  --Password NewSecurePass123!
```

### Image Operations

```bash
# List system images
aliyun ecs DescribeImages \
  --RegionId cn-hangzhou \
  --ImageOwnerAlias system \
  --OSType Linux

# Search for CentOS images
aliyun ecs DescribeImages \
  --RegionId cn-hangzhou \
  --ImageName "CentOS*" \
  --ImageOwnerAlias system
```

### Snapshot Operations

```bash
# Create snapshot
aliyun ecs CreateSnapshot \
  --DiskId d-bp67acfmxazb4ph*** \
  --SnapshotName my-snapshot

# Describe snapshots
aliyun ecs DescribeSnapshots --RegionId cn-hangzhou

# Delete snapshot
aliyun ecs DeleteSnapshot --SnapshotId s-bp67acfmxazb4ph***
```

### Security Group Operations

```bash
# Create security group
aliyun ecs CreateSecurityGroup \
  --RegionId cn-hangzhou \
  --SecurityGroupName my-sg \
  --VpcId vpc-bp67acfmxazb4ph***

# Describe security groups
aliyun ecs DescribeSecurityGroups --RegionId cn-hangzhou

# Authorize inbound rule (SSH) - restrict to specific IP (recommended)
aliyun ecs AuthorizeSecurityGroup \
  --SecurityGroupId sg-bp67acfmxazb4ph*** \
  --RegionId cn-hangzhou \
  --Permissions '[{"IpProtocol":"tcp","PortRange":"22/22","SourceCidrIp":"203.0.113.10/32","Policy":"accept","Priority":"1"}]'

# Authorize inbound rule (HTTP) - open to internet (use with caution)
aliyun ecs AuthorizeSecurityGroup \
  --SecurityGroupId sg-bp67acfmxazb4ph*** \
  --RegionId cn-hangzhou \
  --Permissions '[{"IpProtocol":"tcp","PortRange":"80/80","SourceCidrIp":"0.0.0.0/0","Policy":"accept","Priority":"2"}]'

# Revoke rule by rule ID (recommended)
aliyun ecs RevokeSecurityGroup \
  --SecurityGroupId sg-bp67acfmxazb4ph*** \
  --RegionId cn-hangzhou \
  --SecurityGroupRuleId.1 sgr-bp67acfmxazb4ph***

# Revoke rule using Permissions array (old flat params are deprecated)
aliyun ecs RevokeSecurityGroup \
  --SecurityGroupId sg-bp67acfmxazb4ph*** \
  --RegionId cn-hangzhou \
  --Permissions '[{"IpProtocol":"tcp","PortRange":"22/22","SourceCidrIp":"0.0.0.0/0","Policy":"accept"}]'
```

### Region/Zone Operations

```bash
# Describe regions
aliyun ecs DescribeRegions

# Describe zones in a region
aliyun ecs DescribeZones --RegionId cn-hangzhou
```

## Polling with Waiter

```bash
# Wait for instance to be Running (using --waiter)
aliyun ecs DescribeInstances \
  --RegionId cn-hangzhou \
  --InstanceIds '["i-bp67acfmxazb4ph***"]' \
  --waiter expr='Instances.Instance[0].Status' to=Running timeout=300 interval=5

# Wait for disk to be Available (using --waiter)
aliyun ecs DescribeDisks \
  --RegionId cn-hangzhou \
  --DiskIds '["d-bp67acfmxazb4ph***"]' \
  --waiter expr='Disks.Disk[0].Status' to=Available timeout=120 interval=5
```

> **Note:** `--waiter` may not be available in all `aliyun` CLI versions. Use the manual polling loop below as a universal fallback:

```bash
# Manual polling for instance status (universal compatibility)
for i in $(seq 1 60); do
  STATUS=$(aliyun ecs DescribeInstances \
    --RegionId cn-hangzhou \
    --InstanceIds '["i-bp67acfmxazb4ph***"]' \
    --output cols=Status rows=Instances.Instance[0].Status)
  echo "Attempt $i: Status=$STATUS"
  [ "$STATUS" = "Running" ] && break
  sleep 5
done
```
