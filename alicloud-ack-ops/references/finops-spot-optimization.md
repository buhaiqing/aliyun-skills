# ACK Spot Instance Optimization

Analyze spot instance usage and provide optimization suggestions for ACK clusters.

## Best Practices

| Workload | Recommendation | Risk Control |
|----------|---------------|-------------|
| Batch processing | Use Spot | Multi-AZ + retry |
| Stateless services | Spot + On-demand mix | Hybrid node pool |
| Stateful services | Avoid Spot | Prepaid or on-demand |
| Critical databases | Never Spot | Dedicated node pool |

## CLI Script

```bash
#!/bin/bash
# ack-spot-optimization.sh
# Usage: ./ack-spot-optimization.sh <ClusterId>

CLUSTER_ID="$1"
echo "=== ACK Spot Instance Optimization ==="

# Get node pools
echo ""
echo "### Node Pool Spot Instance Usage ###"
aliyun cs GET /clusters/$CLUSTER_ID/nodepools | jq '.nodepools[] | {name, nodepool_id, spot_strategy, instance_type, desired_size}'

# Check spot instances in cluster
echo ""
echo "### Spot Instances in Cluster ###"
aliyun cs GET /clusters/$CLUSTER_ID/nodes | jq '.nodes[] | select(.spot_strategy=="SpotAsPriceGo" or .spot_strategy=="SpotWithPriceLimit") | {instance_id, instance_type, spot_strategy}'

echo ""
echo "### Recommendations ###"
echo "1. Use Spot instances for batch/stateless workloads"
echo "2. Mix Spot + On-demand for resilience (e.g., 70% Spot + 30% On-demand)"
echo "3. Configure spot-autoscaler-addon for automatic spot instance management"
echo "4. Multi-AZ distribution to reduce spot interruption impact"
```