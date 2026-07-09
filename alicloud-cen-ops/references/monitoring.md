<!-- markdownlint-disable MD013 MD060 MD024 MD022 MD032 -->

# Monitoring & Alerts — CEN/CBN

## Monitoring Scope

CEN monitoring focuses on connectivity, route health, inter-region capacity, attachment status, and traffic visibility. Use CloudMonitor/CMS for metrics and alarms; use CEN flow logs for packet/flow-level analysis.

## Read-Only Health Checks

```bash
aliyun cbn DescribeCens --CenId {{user.cen_id}}
aliyun cbn DescribeTransitRouters --CenId {{user.cen_id}} --RegionId {{user.region}}
aliyun cbn DescribeTransitRouterAttachments --RegionId {{user.region}} --TransitRouterId {{user.transit_router_id}}
aliyun cbn DescribeCenInterRegionBandwidthLimits --CenId {{user.cen_id}}
aliyun cbn DescribeFlowlogs --CenId {{user.cen_id}} --RegionId {{user.region}}
```

## Key Signals

| Signal | Source | Alert Intent |
|--------|--------|--------------|
| Attachment state changes | CEN Describe APIs / ActionTrail | Detect detached/failed attachment |
| Inter-region bandwidth utilization | CloudMonitor / CEN bandwidth APIs | Prevent saturation and packet loss |
| Route table changes | ActionTrail + CEN Describe APIs | Detect risky route updates |
| Route conflict findings | `DescribeRouteConflict` | Block new attachments/routes |
| Flow log volume/anomaly | CEN flow logs in SLS | Identify unexpected traffic drop/spike |
| VBR health check status | `DescribeCenVbrHealthCheck` | Detect Express Connect path failure |

## Flow Logs

Use flow logs for traffic diagnostics. Pre-flight must verify SLS project/logstore and permissions.

```bash
aliyun cbn CreateFlowlog \
  --CenId "{{user.cen_id}}" \
  --RegionId "{{user.region}}" \
  --ProjectName "{{user.sls_project}}" \
  --LogStoreName "{{user.logstore}}"

aliyun cbn ActiveFlowLog --FlowLogId "{{output.flow_log_id}}"
```

Disable/delete flow logs only after confirming retention and audit requirements.

## Alarm Recommendations

| Condition | Suggested Severity | Action |
|-----------|--------------------|--------|
| Attachment not stable for > 5 min | Critical | Freeze route changes; inspect attachment and dependencies |
| Inter-region bandwidth > 80% for 15 min | Warning | Review bandwidth package/limit and traffic split |
| Inter-region bandwidth > 95% for 5 min | Critical | Increase bandwidth or reroute traffic |
| Route conflict detected | Critical | Block deployment; redesign CIDR/routes |
| VBR health check failed | Critical | Check physical circuit/provider and failover path |
| Flow log traffic drops to zero unexpectedly | Warning/Critical | Verify route/SG/NACL/backend status |

## Dashboard Checklist

- CEN inventory: CEN ID, TR count, attachment count, route table count.
- Cross-region links: bandwidth, utilization, peer attachment state.
- Attachments by type: VPC/VBR/VPN/ECR/Peer and state.
- Route changes: ActionTrail event timeline.
- Flow log top talkers and denied/blackholed traffic patterns.

## Delegation

If user asks to create CloudMonitor alarm resources, delegate alarm creation to `alicloud-cms-ops` and pass the metric intent, dimensions, threshold, and notification policy.
