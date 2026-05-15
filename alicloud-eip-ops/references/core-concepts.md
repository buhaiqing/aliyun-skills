# EIP Core Concepts

> **Purpose:** EIP architecture, billing, limits, and resource relationships.

## What is EIP?

Alibaba Cloud EIP (Elastic IP Address) is a **public IP resource** that can be **dynamically associated with and unassociated from** cloud resources. Unlike fixed public IPs, EIPs have an independent lifecycle.

### Supported Bind Targets

| InstanceType | Description | Example |
|--------------|-------------|---------|
| `EcsInstance` | ECS instance | `i-bp1xxxxxxx` |
| `Nat` | NAT Gateway | `ngw-xxxxxxx` |
| `SLBInstance` | Server Load Balancer | `lb-xxxxxxx` |
| `HaVip` | High-Availability Virtual IP | `havip-xxxxxxx` |
| `NetworkInterface` | Elastic Network Interface (ENI) | `eni-xxxxxxx` |
| `Ngw` | Enhanced NAT Gateway (new type) | `ngw-xxxxxxx` |

### EIP Billing Modes

| Mode | Description | Suitable For |
|------|-------------|--------------|
| **PayByBandwidth** | Fixed monthly bandwidth fee, charged by maximum bandwidth | Stable, predictable traffic |
| **PayByTraffic** | Charged by actual GB of data transferred, plus instance fee | Bursty, unpredictable traffic |

### Bandwidth Limits

| Billing Mode | Min | Max | Typical |
|--------------|-----|-----|---------|
| PayByTraffic | 1 Mbps | 200 Mbps | 5-100 Mbps |
| PayByBandwidth | 1 Mbps | 500 Mbps | 5-500 Mbps |

## Resource Lifecycle

```
Allocate → Available → Associate → InUse → Unassociate → Available → Release
   |                            |
   +-- Direct Release ❌        +-- Always Unbind first
```

## EIP Quotas (Default)

| Resource | Default Limit |
|----------|---------------|
| EIPs per region | 20 |
| EIP Bandwidth Plans | 10 |
| EIPs per Bandwidth Plan | 20 |

## Security

- EIP does **not** provide any firewall/security capability
- Security is handled by:
  - **Security Groups** for ECS instances
  - **Network ACLs** for vSwitch-level traffic control
  - **NAT Gateway** for SNAT/DNAT port filtering
- Always verify security rules after EIP binding to avoid exposing services unintentionally.

## Common EIP Use Cases

1. **Direct ECS access:** Bind EIP to ECS for direct internet access
2. **NAT Gateway SNAT source:** Bind EIPs to NAT for outbound internet access for multiple instances
3. **NAT Gateway DNAT target:** Bind EIPs to NAT for inbound port mapping
4. **SLB public endpoint:** Bind EIP to SLB for internet-facing load balancer
5. **High-availability failover:** Use EIP + HaVip for automatic failover scenarios
