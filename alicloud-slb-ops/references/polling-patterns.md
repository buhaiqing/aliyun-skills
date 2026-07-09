# Polling Patterns — SLB/CLB

## Generic Polling Templates

### Load balancer attribute (status or spec field)

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun slb DescribeLoadBalancerAttribute \
    --LoadBalancerId "{{user.load_balancer_id}}" \
    --output cols={{field}} rows={{field}})
  [ "$STATUS" = "{{target_value}}" ] && break
  sleep {{interval}}
done
```

### Load balancer absence (`TotalCount=0`)

```bash
for i in $(seq 1 {{max_retries}}); do
  RESULT=$(aliyun slb DescribeLoadBalancers \
    --RegionId "{{user.region}}" \
    --LoadBalancerId "{{user.load_balancer_id}}" \
    --output cols=TotalCount rows=TotalCount)
  [ "$RESULT" = "0" ] && break
  sleep {{interval}}
done
```

### Listener status by port

```bash
for i in $(seq 1 {{max_retries}}); do
  STATUS=$(aliyun slb DescribeLoadBalancerListeners \
    --LoadBalancerId "{{user.load_balancer_id}}" \
    --output cols=Status rows=Listeners.Listener[?ListenerPort=='{{user.listener_port}}'].Status)
  [ "$STATUS" = "{{target_status}}" ] && break
  sleep {{interval}}
done
```

## Per-Operation Polling Parameters

| Operation | Describe Command | Field / Path | Target | Interval | Max Retries |
|-----------|-----------------|--------------|--------|----------|-------------|
| CreateLoadBalancer | DescribeLoadBalancerAttribute | `LoadBalancerStatus` | `active` | 5s | 24 |
| SetLoadBalancerStatus | DescribeLoadBalancerAttribute | `LoadBalancerStatus` | `{{user.target_status}}` | 5s | 12 |
| ModifyLoadBalancerSpec | DescribeLoadBalancerAttribute | `LoadBalancerSpec` | `{{user.new_load_balancer_spec}}` | 5s | 12 |
| DeleteLoadBalancer | DescribeLoadBalancers | `TotalCount` → `0` | absent | 5s | 24 |
| Create*Listener / StartListener | DescribeLoadBalancerListeners | `Status` (by port) | `running` | 5s | 12 |
| StopListener | DescribeLoadBalancerListeners | `Status` (by port) | `stopped` | 5s | 12 |

> See **Expected State Transitions** table in `SKILL.md` for max-wait budgets per operation.
