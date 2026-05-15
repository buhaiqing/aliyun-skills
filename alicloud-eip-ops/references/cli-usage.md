# CLI — EIP (`aliyun`)

> **Purpose:** `aliyun` CLI command reference for EIP operations.

## Install and config

- Install: `brew install aliyun-cli` or `/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"`
- Credentials via env vars: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- Region via env var: `ALIBABA_CLOUD_REGION_ID`

## Conventions (agent execution)

- Output is **JSON by default** — NO `--output json` needed
- Use `--output cols=...,rows=...` for JMESPath tabular extraction

## Command Map

### EIP Core Operations

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List all EIPs | `aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --output cols=AllocationId,IpAddress,Status,Bandwidth,InstanceId rows=EipAddresses.EipAddress[].{AllocationId:AllocationId,IpAddress:IpAddress,Status:Status,Bandwidth:Bandwidth,InstanceId:InstanceId}` | |
| Allocate EIP | `aliyun vpc AllocateEipAddress --RegionId {{user.region}} --Bandwidth 5 --InternetChargeType PayByTraffic --Name "my-eip"` | Returns AllocationId |
| Describe EIP | `aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}}` | |
| Associate to ECS | `aliyun vpc AssociateEipAddress --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}} --InstanceId {{user.instance_id}} --InstanceType EcsInstance` | |
| Associate to NAT | `aliyun vpc AssociateEipAddress --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}} --InstanceId {{user.nat_gateway_id}} --InstanceType Nat` | |
| Associate to SLB | `aliyun vpc AssociateEipAddress --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}} --InstanceId {{user.slb_id}} --InstanceType SLBInstance` | |
| Unassociate EIP | `aliyun vpc UnassociateEipAddress --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}} --InstanceId {{user.instance_id}} --InstanceType {{user.instance_type}}` | Network interruption warning |
| Modify Bandwidth | `aliyun vpc ModifyEipAddressAttribute --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}} --Bandwidth 100` | |
| Modify Billing | `aliyun vpc ModifyEipAddressAttribute --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}} --InternetChargeType PayByTraffic --Bandwidth 100` | |
| Release EIP | `aliyun vpc ReleaseEipAddress --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --AllocationId {{user.eip_id}}` | Must unbind first |
| Convert NAT IP | `aliyun vpc ConvertNatPublicIpToEip --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --InstanceId {{user.instance_id}}` | Convert ECS NAT public IP |

### EIP Filtering

| Goal | Example Command | Notes |
|------|-----------------|-------|
| Filter by status | `aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --Status Available` | Available/InUse |
| Filter by bound inst | `aliyun vpc DescribeEipAddresses --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --InstanceId {{user.instance_id}}` | Find EIP for instance |

### EIP Bandwidth Plans

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List Plans | `aliyun vpc DescribeCommonBandwidthPackages --RegionId {{env.ALIBABA_CLOUD_REGION_ID}}` | |
| Create Plan | `aliyun vpc CreateCommonBandwidthPackage --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --Bandwidth 100 --Name "my-bw-plan"` | Returns BandwidthPackageId |
| Add EIP to Plan | `aliyun vpc AddCommonBandwidthPackageIp --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --BandwidthPackageId {{user.bandwidth_package_id}} --IpInstanceId {{user.eip_id}}` | |
| Remove EIP from Plan | `aliyun vpc RemoveCommonBandwidthPackageIp --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --BandwidthPackageId {{user.bandwidth_package_id}} --IpInstanceId {{user.eip_id}}` | |
| Delete Plan | `aliyun vpc DeleteCommonBandwidthPackage --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --BandwidthPackageId {{user.bandwidth_package_id}}` | Remove all EIPs first |
