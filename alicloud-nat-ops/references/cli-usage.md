# CLI — NAT (`aliyun`)

> **Purpose:** `aliyun` CLI command reference for NAT Gateway operations.

## Install and config

- Install: `brew install aliyun-cli` or `/bin/bash -c "$(curl -fsSL https://aliyuncli.alicdn.com/install.sh)"`
- Credentials via env vars: `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- Region via env var: `ALIBABA_CLOUD_REGION_ID`

## Conventions (agent execution)

- Output is **JSON by default** — NO `--output json` needed
- Use `--output cols=...,rows=...` for JMESPath tabular extraction

## Command Map

### NAT Gateway Operations

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List NAT Gateways | `aliyun vpc DescribeNatGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --output cols=NatGatewayId,Name,Status,Spec,VpcId rows=NatGateways.NatGateway[].{NatGatewayId:NatGatewayId,Name:Name,Status:Status,Spec:Spec,VpcId:VpcId}` | |
| Create Enhanced NAT | `aliyun vpc CreateNatGateway --RegionId {{user.region}} --VpcId {{user.vpc_id}} --NatType Enhanced --VSwitchId {{user.vswitch_id}} --Name "my-nat" --BillingMethod PayBySpec` | Returns NatGatewayId |
| Describe NAT | `aliyun vpc DescribeNatGateways --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}` | |
| Modify NAT Name | `aliyun vpc ModifyNatGatewayAttribute --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}} --Name "new-name"` | |
| Delete NAT | `aliyun vpc DeleteNatGateway --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}` | Delete SNAT/DNAT first |

### SNAT Operations

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List SNAT Entries | `aliyun vpc DescribeSnatTableEntries --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}} --output cols=SnatEntryId,SnatIp,SourceCIDR rows=SnatTableEntries.SnatTableEntry[].{SnatEntryId:SnatEntryId,SnatIp:SnatIp,SourceCIDR:SourceCIDR}` | |
| Create SNAT (CIDR) | `aliyun vpc CreateSnatEntry --RegionId {{user.region}} --NatGatewayId {{user.nat_gateway_id}} --SnatIp "{{user.eip_address}}" --SourceCIDR "{{user.source_cidr}}" --SnatEntryName "snat-entry-1"` | CIDR-level SNAT |
| Create SNAT (vSwitch) | `aliyun vpc CreateSnatEntry --RegionId {{user.region}} --NatGatewayId {{user.nat_gateway_id}} --SnatIp "{{user.eip_address}}" --VSwitchId {{user.vswitch_id}} --SnatEntryName "snat-vswitch-1"` | vSwitch-level SNAT |
| Delete SNAT | `aliyun vpc DeleteSnatEntry --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --SnatEntryId {{user.snat_entry_id}}` | |

### DNAT / Forward Operations

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List DNAT Entries | `aliyun vpc DescribeForwardTableEntries --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}} --output cols=ForwardEntryId,IpProtocol,ExternalIp,ExternalPort rows=ForwardTableEntries.ForwardTableEntry[].{ForwardEntryId:ForwardEntryId,IpProtocol:IpProtocol,ExternalIp:ExternalIp,ExternalPort:ExternalPort}` | |
| Create DNAT (TCP) | `aliyun vpc CreateForwardEntry --RegionId {{user.region}} --NatGatewayId {{user.nat_gateway_id}} --IpProtocol TCP --ExternalIp "{{user.external_ip}}" --ExternalPort "{{user.external_port}}" --InternalIp "{{user.internal_ip}}" --InternalPort "{{user.internal_port}}" --ForwardEntryName "dnat-web"` | Port mapping |
| Create DNAT (UDP) | `aliyun vpc CreateForwardEntry --RegionId {{user.region}} --NatGatewayId {{user.nat_gateway_id}} --IpProtocol UDP --ExternalIp "{{user.external_ip}}" --ExternalPort "{{user.external_port}}" --InternalIp "{{user.internal_ip}}" --InternalPort "{{user.internal_port}}" --ForwardEntryName "dnat-dns"` | UDP port mapping |
| Delete DNAT | `aliyun vpc DeleteForwardEntry --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --ForwardEntryId {{user.forward_entry_id}}` | |

### FULLNAT Operations

| Goal | Example Command | Notes |
|------|-----------------|-------|
| List FULLNAT | `aliyun vpc DescribeFullNatEntries --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --NatGatewayId {{user.nat_gateway_id}}` | |
| Create FULLNAT | `aliyun vpc CreateFullNatEntry --RegionId {{user.region}} --NatGatewayId {{user.nat_gateway_id}} --FullNatIp "{{user.fullnat_ip}}" --DestinationCidrBlock "{{user.dest_cidr}}" --IpProtocol TCP --InternalIp "{{user.internal_ip}}" --InternalPort "{{user.internal_port}}"` | |
| Delete FULLNAT | `aliyun vpc DeleteFullNatEntry --RegionId {{env.ALIBABA_CLOUD_REGION_ID}} --FullNatEntryId {{user.fullnat_entry_id}}` | |

### jq Best Practice (JSON Processing)

- Use `jq` for complex JSON transformations after `aliyun` commands
- Use `[]?` to safely handle empty/null arrays: `.Items.Item[]?`
- Use `--PageSize` to control result sets: `--PageSize 50`
- Example:
```bash
aliyun ecs DescribeInstances --PageSize 50 | jq '{total: .TotalCount, items: [.Items.Item[]? | {id: .Id, name: .Name}]}'
```

