# Core Concepts — Alibaba Cloud SLB (Classic Load Balancer)

## What is SLB/CLB?

Server Load Balancer (SLB), also known as Classic Load Balancer (CLB), is Alibaba
Cloud's layer-4 and layer-7 load balancing service that distributes incoming traffic
across multiple backend servers to improve service availability, elasticity, and
fault tolerance.

## Product Variants

| Variant | API Version | Use Case | Layer |
|---------|-------------|----------|-------|
| **CLB** (Classic Load Balancer) | SLB 2014-05-15 | Traditional load balancing | L4/L7 |
| **ALB** (Application Load Balancer) | ALB 2020-06-16 | Advanced HTTP/HTTPS routing | L7 |
| **NLB** (Network Load Balancer) | NLB 2022-04-30 | Ultra-low latency TCP/UDP | L4 |

> This skill covers **CLB only**. ALB and NLB use different API surfaces and require
> separate skills.

## Key Concepts

### Load Balancer Instance

The core resource that receives and distributes traffic:

- **LoadBalancerId**: Unique identifier (e.g., `lb-bp67acfmxazb4ph***`)
- **Address**: The IP address assigned to the instance
- **AddressType**: `internet` (public) or `intranet` (private)
- **NetworkType**: `vpc` or `classic`
- **Status**: `active` or `inactive`
- **LoadBalancerSpec**: Instance specification defining performance capacity
  - `slb.s1.small`: Standard I
  - `slb.s2.small`: Standard II
  - `slb.s2.medium`: Advanced I
  - `slb.s3.small`: Advanced II
  - `slb.s3.medium`: Superior I
  - `slb.s3.large`: Superior II
- **DeleteProtection**: `on` or `off` — prevents accidental deletion
- **ModificationProtectionStatus**: `ConsoleProtection` or `NonProtection`

### Listener

A listener checks for connection requests and forwards them to backend servers:

- **ListenerPort**: Frontend port (1-65535)
- **BackendServerPort**: Backend port (1-65535)
- **Protocol**: `tcp`, `udp`, `http`, `https`
- **Bandwidth**: Bandwidth limit in Mbps (-1 = unlimited)
- **Scheduler**: `wrr` (weighted round robin) or `rr` (round robin)
- **HealthCheck**: `on` or `off`
- **Status**: `running` or `stopped`

### Virtual Server Group (VServer Group)

A collection of backend servers with custom ports and weights:

- **VServerGroupId**: Unique identifier
- **VServerGroupName**: Human-readable name
- **BackendServers**: Array of backend server configurations
  - `ServerId`: ECS/ENI/ECI instance ID
  - `Weight`: 0-100 (0 = no traffic)
  - `Type`: `ecs` (default), `eni`, `eci`
  - `Port`: Backend port
  - `Description`: Optional description

> VServer groups allow different listeners to route to different backend ports
> on the same ECS instance.

### Default Server Group

The default set of backend servers for a load balancer, used when no vserver group
is specified for a listener.

### Master-Slave Server Group

A high-availability group with one master and one or more slave servers. When the
master fails, traffic is automatically routed to a slave.

### Certificate

SSL/TLS certificates for HTTPS listeners:

- **ServerCertificate**: The public certificate
- **PrivateKey**: The private key (PEM format)
- **ServerCertificateId**: Unique identifier after upload
- **CA Certificate**: Optional CA certificate for client authentication

### Access Control List (ACL)

IP-based access control for listeners:

- **AclId**: Unique identifier
- **AclName**: Human-readable name
- **AclEntrys**: Array of IP/CIDR entries with optional comments

### Forwarding Rule

Layer-7 routing rules for HTTP/HTTPS listeners:

- **RuleId**: Unique identifier
- **RuleName**: Human-readable name
- **Domain**: Matched domain name
- **Url**: Matched URL pattern (supports wildcards)
- **VServerGroupId**: Target vserver group

## Health Check

SLB performs health checks on backend servers to ensure traffic is only routed to
healthy instances:

- **TCP Health Check**: Attempts TCP connection to backend port
- **HTTP Health Check**: Sends HTTP requests and checks response status
- **HealthCheckConnectPort**: Port used for health checks (can differ from backend port)
- **HealthCheckInterval**: Check interval in seconds (default 2s)
- **HealthyThreshold**: Consecutive successes to mark healthy (default 3)
- **UnhealthyThreshold**: Consecutive failures to mark unhealthy (default 3)
- **HealthCheckTimeout**: Response timeout in seconds (default 5s)

## Session Persistence (Sticky Session)

Ensures requests from the same client are routed to the same backend server:

- **TCP/UDP**: Based on client IP (`PersistenceTimeout` in seconds)
- **HTTP/HTTPS**: Based on Cookie
  - `insert`: SLB inserts a cookie
  - `server`: SLB rewrites the application's cookie

## Billing

- **InstanceChargeType**: `PayBySpec` (pay by specification) or `PayByCLCU` (pay by usage)
- **InternetChargeType**: `paybytraffic` or `paybybandwidth`
- **PayType**: `PayOnDemand` (pay-as-you-go) or `PrePay` (subscription)

> **Note:** CLB subscription instances stopped new purchases on 2024-12-01.
> Only pay-as-you-go instances can be created.

## Quotas and Limits

| Resource | Default Limit |
|----------|---------------|
| SLB instances per region | 60 |
| Listeners per SLB | 50 |
| VServer groups per SLB | 100 |
| Backend servers per vserver group | 200 |
| Certificates per region | 100 |
| ACLs per region | 50 |
| ACL entries per ACL | 300 |
| Forwarding rules per listener | 20 |

## Important Notes

- An SLB instance must be in `active` state before creating listeners
- Deleting an SLB instance automatically deletes all its listeners and rules
- VServer groups must not be referenced by any listener before deletion
- Certificates must not be referenced by any HTTPS listener before deletion
- ACLs must not be referenced by any listener before deletion
- Changing instance spec may cause brief connection interruption
- Health check configurations are listener-specific
