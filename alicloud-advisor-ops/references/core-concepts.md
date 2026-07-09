# Advisor — Core Concepts

## What is Intelligent Advisor?

Alibaba Cloud Intelligent Advisor (智能顾问) is a managed cross-product
**inspection and recommendation** service. It does **not** run user
workloads; it observes them.

Advisor's job is to answer three questions:

1. **What's risky in my account?** — security, stability, performance
   violations across all cloud products.
2. **What can I save?** — idle, oversized, or underutilized resources
   with savings estimates.
3. **What should I do next?** — concrete remediation actions per advice.

## The Inspection Model

```
[ Schedule (default daily)        ]
[ User-triggered Refresh          ]
[ Resource change event           ]  -- triggers scan
            |
            v
     +---------------+
     |  Inspection   |  per product / per check
     |   engine      |  (managed by Alibaba Cloud)
     +-------+-------+
             |
             v
     +---------------+
     |   Advice      |  one per issue found
     |   + CheckId   |  the rule that fired
     |   + Severity  |  Critical / Warning / Info
     |   + Resource  |  the affected resource
     |   + Action    |  remediation hint
     +-------+-------+
             |
             v
     +---------------+
     |   Storage     |  history retained per plan
     +---------------+
             |
             v
     [ aliyun advisor describe-advices ]   <-- this skill's read path
```

Key terms:

| Term | Definition |
|------|------------|
| **Advice** | A single issue found by Advisor. One resource may have multiple advices. |
| **Check (CheckId)** | The rule that produced the advice (e.g. `Ecs.SecurityGroup.OpenPort22`). |
| **Severity** | `Critical`, `Warning`, `Info` — the urgency of remediation. |
| **CheckPlan** | A grouping of checks (e.g. "Security", "Cost", "Performance"). |
| **Resource** | The cloud resource the advice refers to (instance, bucket, etc.). |
| **Inspection Task** | An async run of the scan engine; produces a `TaskId` for polling. |
| **Dimension** | Cost or Performance — the lens through which a check evaluates resources. |

## Advice Lifecycle

```
[ Check rule evaluates resource ]
            |
            v
   [   Advice produced   ]  <-- visible via DescribeAdvices
            |
            v
   [ User reads / acts   ]  <-- delegate to per-product ops skill
            |
            v
   [ Resource fixed       ]
            |
            v
   [ Next inspection:     ]  <-- advice disappears (re-evaluated)
   [   advice gone        ]
```

Notes:

- Advices are **regenerated** on every inspection, not persisted
  incrementally. The "history" is a snapshot of past inspections.
- An advice's `AdviceId` is **stable only within a single inspection**.
  Across inspections, the same problem may have different `AdviceId`s.
  For long-term tracking, use `(CheckId, ResourceId, InspectionTime)`
  as a composite key.

## Inspection Triggers

Advisor runs inspections on three triggers:

1. **Scheduled** — daily by default for paid plans; configurable per
   product. Free tier has reduced frequency.
2. **User-triggered** — `RefreshAdvisorCheck` and
   `RefreshAdvisorCostCheck`. Triggers a fresh scan immediately.
3. **Resource-change event** — when a resource is created/modified,
   Advisor's change-feed picks it up. (No API; managed by the service.)

## Severity Semantics

| Severity | Meaning | Action |
|----------|---------|--------|
| `Critical` | Active risk; security/stability exposure or significant cost leak | Fix within days |
| `Warning` | Suboptimal configuration; risk if not addressed | Fix within weeks |
| `Info` | Best-practice suggestion; improvement opportunity | Fix when convenient |

Severity is set by the check rule, not the resource. The same resource
issue (e.g. open SSH port) is always `Critical` for the
`Ecs.SecurityGroup.OpenPort22` check.

## Cost Optimization Model

The cost optimization API surface (`DescribeCost*` and
`RefreshAdvisorCostCheck`) uses a separate pipeline from the health
advice pipeline. The two have **different** check IDs and inspection
schedules.

```
[ Cost check engine ]  -- separate from health checks
        |
        v
[ Cost advice: idle resource, oversized spec, ... ]
        |
        v
[ $.Overview.TotalSavings (estimated monthly savings in CNY/USD) ]
```

Each cost advice includes:

- The current spec / configuration.
- The recommended spec / configuration.
- Estimated monthly savings.
- The action to take (e.g. "downgrade to ecs.g6.large").

Cost optimization advices are **recommendations only**. The user must
run the actual spec change via the relevant per-product ops skill
(`alicloud-ecs-ops`, `alicloud-rds-ops`, etc.). Advisor never executes
changes itself.

## Inspection Task Lifecycle

```
RefreshAdvisorCheck
    |
    v
$.TaskId returned
    |
    v
GetInspectProgress  (poll every 30s, max 10 min)
    |
    +---> Status: Pending
    +---> Status: Running (Progress 0-100)
    +---> Status: Finished  <-- DescribeAdvices now reflects new state
    +---> Status: Failed    <-- InvestigateInspectError (consult service docs)
```

Tasks have a finite retention window (typically 1-2 hours). After
expiry, `GetTaskStatusById` returns `TaskNotFound`.

## Multi-Account Support

Advisor supports RAM role assumption via `--assume-aliyun-id`. This is
useful for:

- Inspecting sub-accounts from a master account.
- MSP / partner scenarios where one operator inspects many tenants.

When you call with `--assume-aliyun-id`, the response includes
`AdviserAccountId` and `CheckId` scoped to the assumed account.

## Limits and Quotas

| Item | Free Tier | Paid Plans |
|------|-----------|------------|
| Inspection frequency | Daily | Configurable (hourly+) |
| History retention | 7 days | 30-90 days (plan-dependent) |
| Concurrent inspection tasks | 1 | Up to 3 |
| API call quota | Low (subject to throttling) | Higher |

Specific quotas are not published; throttling is the user-visible
symptom. See [Troubleshooting](troubleshooting.md) for throttle handling.

## Cross-Skill Architecture Position

```
+----------------+      +----------------+      +----------------+
| alicloud-cms-  |      | alicloud-      |      | alicloud-      |
| ops            |      | advisor-ops    |      | actiontrail-   |
| (raw metrics)  |      | (this skill)   |      | ops            |
|                |      | (advice +      |      | (event log)    |
|                |      |  cost recs)    |      |                |
+-------+--------+      +-------+--------+      +--------+-------+
        |                       |                        |
        |   drill to metric     |                        |
        +---------------------->|                        |
        |                       |                        |
        |   ask "why this       |                        |
        |   advice?"            |                        |
        |<----------------------+                        |
        |                                                |
        |   cross-check: "did this op actually happen?"  |
        +------------------------------------------------>
```

Advisor sits at the **aggregation layer**: it interprets raw metrics
(CMS), events (ActionTrail), and resource state into actionable advice.
For deep dives, delegate to the per-skill (`cms-ops` for raw data,
`actiontrail-ops` for events, `ecs-ops`/`rds-ops`/etc. for remediation).

## What Advisor is NOT

- **Not a SIEM** — for security event correlation, use ActionTrail.
- **Not a real-time monitor** — for time-series metrics, use CMS.
- **Not an auto-remediator** — for executing fixes, use per-product ops skills.
- **Not a billing system** — for invoices and spend history, use `alicloud-billing-ops`.
- **Not a cost explorer** — for detailed spend breakdown by tag/region,
  use `alicloud-billing-ops` Cost Analysis.

## Further Reading

- [OpenAPI overview](https://help.aliyun.com/zh/advisor/developer-reference/api-advisor-2018-01-20-overview)
- [Console quickstart](https://help.aliyun.com/zh/advisor/getting-started/start-using-advisor)
- [Severity definitions](https://help.aliyun.com/zh/advisor/user-guide/severity-levels)
- [Cost check items](https://help.aliyun.com/zh/advisor/user-guide/cost-check-items)
