# Core Concepts — Alibaba Cloud ActionTrail (操作审计)

## What is ActionTrail?

ActionTrail (操作审计) is Alibaba Cloud's audit logging service that monitors and records
API calls and user activities across all Alibaba Cloud services. It captures operations
performed via the console, OpenAPI, SDKs, and CLI tools, providing a complete audit trail
for security analysis, resource change tracking, and compliance auditing.

## Key Concepts

### Trail (跟踪)

A trail is the core configuration resource that defines how and where to deliver audit
events. Each trail specifies:

- **Name**: Unique identifier (6-36 chars, lowercase start, alphanumeric/hyphen/underscore)
- **Delivery destination**: OSS bucket, SLS project, or MaxCompute project
- **Event scope**: All regions or specific regions
- **Event type**: Read events, Write events, or All events
- **Organization trail**: Multi-account trail for resource directory members

**Limits:**
- Maximum 5 trails per region per account
- Trails are created in **disabled** state by default
- Must call `StartLogging` to enable event delivery

### Event (事件)

An event records a single operation performed on an Alibaba Cloud resource. Each event
contains:

- **Event ID**: Unique identifier
- **Event Name**: The API operation name (e.g., `CreateInstance`, `DeleteInstances`)
- **Event Source**: The service that generated the event (e.g., `ecs.aliyuncs.com`)
- **Event Type**: `ApiCall`, `ConsoleOperation`, `AliyunServiceEvent`, `PasswordReset`,
  `ConsoleSignin`, `ConsoleSignout`
- **User Identity**: Who performed the operation (RAM user, root account, STS, etc.)
- **Resource Info**: Which resources were affected
- **Request Parameters**: The API request details
- **Response Elements**: The API response details
- **Timestamp**: When the operation occurred (ISO 8601 UTC)

### Event Types

| Type | Description |
|------|-------------|
| **ApiCall** | API calls made via OpenAPI, SDK, or CLI |
| **ConsoleOperation** | Operations performed through the Alibaba Cloud console |
| **AliyunServiceEvent** | Operations performed by Alibaba Cloud services on your behalf |
| **PasswordReset** | Password reset events |
| **ConsoleSignin** | Console login events |
| **ConsoleSignout** | Console logout events |

### Event Retention

- **Default**: 90 days of event history available in the console and via LookupEvents API
- **Extended**: Create a trail to deliver events to OSS, SLS, or MaxCompute for
  long-term storage and analysis

### Delivery Destinations

| Destination | Use Case | Storage Format |
|-------------|----------|----------------|
| **OSS** (Object Storage Service) | Long-term archival, cost-effective storage | Gzip-compressed JSON files |
| **SLS** (Log Service) | Real-time analysis, alerting, dashboard | Log entries in Logstore |
| **MaxCompute** | Big data analytics, complex queries | Table storage |

### Insight (事件洞察)

Insight provides intelligent analysis of event patterns to detect anomalies.
ActionTrail supports **7 Insight types**:

| InsightType | Detection Scenario | Real-World Example |
|-------------|-------------------|-------------------|
| `IpInsight` | Operations from unfamiliar IP addresses | Employee's AccessKey stolen — hacker makes API calls from a new region |
| `ApiCallRateInsight` | Unusual API call volume changes | Offboarding employee bulk-deletes resources, causing call rate spike |
| `ApiErrorRateInsight` | Unusual API error rate spikes | Deleted resource has hidden dependency — dependent service calls fail |
| `AkInsight` | Unusual AccessKey call patterns | Stolen AK used at abnormal hours or from unusual services |
| `PolicyChangeInsight` | Permission/policy changes | Unauthorized user grants themselves admin privileges |
| `PasswordChangeInsight` | Password change events | Attacker resets account password after compromising credentials |
| `TrailConcealmentInsight` | Trail disable/deletion attempts | Attacker disables audit trail to cover tracks after malicious activity |

**Key behaviors:**
- Insight events are generated **at least 24 hours** after enabling
- Analysis is based on the **past 7 days** of historical management events
- Insight events are retained for **90 days**
- You can query insight events via `LookupInsightEvents` API or CLI

### AccessKey Audit

ActionTrail provides specialized APIs to audit AccessKey usage:

- **GetAccessKeyLastUsedInfo**: Last used time, service, and IP for an AccessKey
- **GetAccessKeyLastUsedEvents**: Last events triggered by an AccessKey
- **GetAccessKeyLastUsedIps**: Last IPs used by an AccessKey
- **GetAccessKeyLastUsedProducts**: Last services accessed by an AccessKey
- **GetAccessKeyLastUsedResources**: Last resources accessed by an AccessKey

### Data Event Selector

Data event selectors allow you to configure which data-level operations (e.g., object
read/write in OSS) to collect, in addition to management events.

### Advanced Query

Advanced query provides SQL-based event search capabilities with pre-built query
scenarios and templates for common audit use cases.

### Data Replenishment (数据回补)

Data replenishment jobs allow you to backfill historical events (up to 90 days) to
configured delivery destinations.

## Architecture

```
User Actions (Console/API/SDK/CLI)
        │
        ▼
┌─────────────────┐
│   ActionTrail   │
│   Service       │
│                 │
│  ┌───────────┐  │
│  │  Events   │  │  ← 10-minute capture window
│  └─────┬─────┘  │
└────────┼────────┘
         │
         ▼
┌──────────────────────────────────────┐
│         Delivery (via Trail)         │
│                                      │
│  ┌─────┐  ┌─────┐  ┌──────────┐     │
│  │ OSS │  │ SLS │  │MaxCompute│     │
│  └─────┘  └─────┘  └──────────┘     │
└──────────────────────────────────────┘
```

## Limits and Quotas

| Resource | Limit |
|----------|-------|
| Trails per region | 5 |
| Trail name length | 6-36 characters |
| LookupEvents rate | 2 calls/second |
| LookupEvents MaxResults | 0-50 per call |
| Event retention (default) | 90 days |
| LookupEvents time range | Max 30 days span, within 90 days |
| Data event selectors per trail | 10 |
| Insight types per account | 7 (IpInsight, ApiCallRateInsight, ApiErrorRateInsight, AkInsight, PolicyChangeInsight, PasswordChangeInsight, TrailConcealmentInsight) |
| Insight event generation delay | ~24 hours after enabling |
| Insight event retention | 90 days |

## Regions

ActionTrail is available in all major Alibaba Cloud regions. Each region has its own
endpoint: `actiontrail.[region_id].aliyuncs.com`.

Global events (e.g., RAM operations, console login) are stored in a configurable
global events storage region.

## Compliance Best Practices

### 1. Full-Coverage Trail Configuration

To meet compliance requirements (e.g.,等保2.0):

- Set `TrailRegion` to `All` — ensures events from all current and future regions are captured
- Set `EventRW` to `All` — captures both read and write events
- Enable logging immediately after creation with `StartLogging`

### 2. Long-Term Event Storage

- Default retention is **90 days**
- Create a trail with **OSS delivery** for cost-effective long-term archival
- Create a trail with **SLS delivery** for real-time analysis and alerting

### 3. Event Security

| Security Measure | Configuration | Scope |
|-----------------|---------------|-------|
| **Encryption at rest** | SSE-KMS (OSS) or KMS service key (SLS) | Configure on OSS/SLS side |
| **Data immutability** | OSS WORM (Write Once Read Many) policy | Configure on OSS side |
| **Access control** | Least-privilege RAM policies for OSS/SLS | Configure on RAM side |
| **Admin权限管控** | Restrict `AliyunActionTrailFullAccess` to minimal users | Configure on RAM side |

### 4. Anomaly Detection

Enable Insight types for automated anomaly detection:
- `IpInsight` — detect AccessKey theft from unfamiliar IPs
- `ApiCallRateInsight` — detect unusual resource operation patterns
- `ApiErrorRateInsight` — detect cascading failures from resource changes
- `AkInsight` — detect unusual AccessKey usage patterns
- `PolicyChangeInsight` — detect unauthorized privilege escalation
- `PasswordChangeInsight` — detect account compromise
- `TrailConcealmentInsight` — detect audit trail tampering

## Billing

- **Event recording and 90-day retention**: Free
- **Event delivery to OSS/SLS/MaxCompute**: Charged according to the destination
  service's pricing
- **Data replenishment**: Charged based on the volume of events processed