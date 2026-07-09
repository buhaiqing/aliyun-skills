# NAT Core Concepts

> **Purpose:** NAT Gateway architecture, types, billing, SNAT/DNAT mechanics, and limits.

## What is NAT Gateway?

NAT (Network Address Translation) Gateway provides network address translation services for cloud resources in a VPC. It enables:
- **SNAT (Source NAT):** Private instances access the internet via NAT
- **DNAT (Destination NAT):** External traffic reaches private instances via port mapping
- **FULLNAT:** Bidirectional NAT — source and destination IPs both translated

## NAT Gateway Types

| Type | Description | Availability Zone | Recommended |
|------|-------------|-------------------|-------------|
| **Enhanced (增强型)** | Single-AZ, better performance, vSwitch-level SNAT, supports more SNAT IPs | Tied to a specific vSwitch | ✅ Yes — default choice |
| **Normal (普通型)** | Multi-AZ support, lower performance, deprecated | VPC-scoped | ❌ Legacy |

## SNAT (Source NAT)

### How SNAT Works

```
Private ECS 10.0.1.5 → SNAT → EIP 1.2.3.4 → Internet
                                            Internet → EIP 1.2.3.4 → SNAT → Private ECS 10.0.1.5
```

### SNAT Source Configurations

| Mode | Description | Connections per EIP |
|------|-------------|---------------------|
| vSwitch-level SNAT | All instances in a vSwitch use the EIP | ~30K per EIP |
| CIDR-level SNAT | Specific CIDR range uses the EIP | ~30K per EIP |

### Scaling SNAT Capacity

Multiple EIPs can be added to a NAT Gateway for SNAT. Total SNAT connections scale with EIP count:

| EIP Count | Max Concurrent Connections (approx.) |
|-----------|--------------------------------------|
| 1 EIP | ~30,000 |
| 2 EIPs | ~60,000 |
| 4 EIPs | ~120,000 |

## DNAT (Destination NAT / Forward Entry)

### How DNAT Works

```
Internet → EIP 1.2.3.4:8080 → DNAT → 10.0.1.5:80
```

### DNAT Fields

| Field | Description | Example |
|-------|-------------|---------|
| Protocol | TCP, UDP, or Any (ip) | TCP |
| External IP | The EIP public IP | 47.100.x.x |
| External Port | Port exposed on EIP | 8080 |
| Internal IP | Private IP of target ECS | 10.0.1.5 |
| Internal Port | Port on target ECS | 80 |

**Example:** External TCP traffic to 47.100.x.x:8080 is forwarded to 10.0.1.5:80.

## FULLNAT

FULLNAT translates both source and destination IPs:
- Source IP: Private IP → EIP (like SNAT)
- Destination IP: Internal service IP → Real server IP (like DNAT)
- Used for advanced load balancing and service mesh scenarios

## Resource Lifecycle

```
Create → Creating → Available → Delete
                        ↑
              SNAT/DNAT Entries → EIPs bound
                        ↓
            Delete ALL entries first!
            Unbind ALL EIPs first!
```

## Quotas (Default)

| Resource | Default Limit |
|----------|---------------|
| NAT Gateways per VPC | 10 |
| SNAT entries per NAT | 200 |
| DNAT entries per NAT | 200 |
| EIPs per NAT Gateway | 20 |

## Billing

### Enhanced NAT Gateway

| Fee Type | Description |
|----------|-------------|
| **Instance fee** | Hourly charge based on spec (Small/Medium/Large/XLarge) |
| **CU fee** | Charged per connection unit, based on actual connections |
| **EIP fee** | Associated EIPs billed separately (EIP instance + bandwidth) |

### Billing Modes

| Mode | Description |
|------|-------------|
| **PayBySpec** | Fixed hourly rate, capped bandwidth |
| **PayByActualUsage** | Pay for actual CU + instance usage — scales automatically |

## Common NAT Use Cases

1. **Internet access for private instances:** SNAT enables ECS/RDS in VPC to access internet
2. **Exposing internal services:** DNAT maps public ports to private service endpoints
3. **Multi-account NAT sharing:** NAT Gateway shared across accounts using Resource Access Manager
4. **Outbound proxy:** Centralized outbound access with audit capabilities (FlowLog)
5. **Development environment sharing:** Multiple dev environments share one NAT Gateway's internet access

## Security Considerations

- **SNAT only:** Outbound access only, no inbound exposure — safest pattern
- **DNAT opens ports:** Each DNAT entry exposes an internal port to the internet
- **Security groups:** DNAT-bypasses security groups; use Network ACLs for additional filtering
- **Port mapping:** Avoid mapping well-known ports (22, 3306) directly to internet
- **EIP cleanup:** Unbind EIPs before deleting NAT to avoid orphaned EIP charges
