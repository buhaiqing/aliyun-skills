# Core Concepts — Alibaba Cloud ECS

## What is ECS?

Elastic Compute Service (ECS) is Alibaba Cloud's Infrastructure-as-a-Service (IaaS) offering that provides scalable virtual servers in the cloud.

## Key Concepts

### Instance
A virtual server in the cloud. Each instance has:
- **Instance ID**: Unique identifier (e.g., `i-bp67acfmxazb4ph***`)
- **Instance Type**: Hardware configuration (CPU, memory) — e.g., `ecs.g7.large`
- **Image**: OS template used to create the instance
- **Status**: `Pending`, `Starting`, `Running`, `Stopping`, `Stopped`, `Expired`, `Deleted`
  - `Pending`: Instance is being created
  - `Starting`: Instance is booting up
  - `Running`: Instance is operational
  - `Stopping`: Instance is shutting down
  - `Stopped`: Instance is powered off (required for delete, resize, password reset)
  - `Expired`: Instance has expired (pay-as-you-go or subscription ended)
  - `Deleted`: Instance has been deleted (may appear briefly in describe results)

### Disk
Block-level storage volumes:
- **System Disk**: OS installation, mandatory, lifecycle-bound to instance
- **Data Disk**: Additional storage, can be attached/detached independently
- **Disk Categories**:
  - `cloud`: Basic cloud disk (HDD)
  - `cloud_efficiency`: High-efficiency cloud disk (SATA SSD)
  - `cloud_ssd`: Standard SSD
  - `cloud_essd`: Enhanced SSD (ESSD), highest performance
  - `cloud_auto`: ESSD AutoPL, auto-scales performance based on workload

### Image
OS template used to create instances:
- **Public Image**: Official images provided by Alibaba Cloud
- **Custom Image**: User-created from existing instances
- **Shared Image**: Shared from other Alibaba Cloud accounts
- **Marketplace Image**: Third-party images from Alibaba Cloud Marketplace

### Snapshot
Point-in-time backup of a disk:
- Used for data backup and disaster recovery
- Can be used to create custom images
- Supports incremental snapshots

### Security Group
Virtual firewall for instances:
- Controls inbound and outbound traffic
- Rules defined by protocol, port range, source/destination CIDR
- Instances in the same security group can communicate by default

### VPC / VSwitch
Virtual network environment:
- **VPC**: Isolated private network
- **VSwitch**: Subnet within a VPC, bound to a specific zone
- ECS instances must be created in a VSwitch (VPC mode)

## Instance Lifecycle

```
CreateInstance → Pending → Starting → Running
                                    ↓
                              StopInstance
                                    ↓
                                Stopped
                                    ↓
                              StartInstance
                                    ↓
                                Running
                                    ↓
                              DeleteInstance
                                    ↓
                                Deleted
```

## Important Notes

- An instance must be in `Stopped` state before it can be deleted
- Disks must be detached before deletion
- Snapshots are region-specific
- Security group rules take effect immediately
