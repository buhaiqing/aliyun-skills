# Redis Intelligent Inspection

Execute a comprehensive health check for Redis/Tair instances. Combines instance status, CMS metrics, slow logs, security config, and backup status.

## CLI Script

```bash
#!/bin/bash
# redis-intelligent-inspection.sh
# Usage: ./redis-intelligent-inspection.sh <InstanceId> <RegionId>

INSTANCE_ID="$1"
REGION="$2"
SCORE=0

echo "=== Redis/Tair Intelligent Inspection ==="
echo "Instance: $INSTANCE_ID"
echo "Region: $REGION"
echo ""

# 1. Instance status check
STATUS=$(aliyun r-kvstore describe-instances \
  --RegionId "$REGION" \
  --InstanceId "$INSTANCE_ID" \
  --output cols=InstanceStatus rows=Instances.KVStoreInstance[0].InstanceStatus)
echo "[1/5] Instance Status: $STATUS"
[ "$STATUS" = "Normal" ] && SCORE=$((SCORE + 20))

# 2. CPU usage check
CPU=$(aliyun cms DescribeMetricList \
  --Namespace acs_kvstore_dashboard \
  --MetricName CpuUsage \
  --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
  --Period 60 \
  --StartTime "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=Average rows=Datapoints[0].Average 2>/dev/null || echo "N/A")
echo "[2/5] CPU Usage: $CPU%"

# 3. Slow log check
SLOW_COUNT=$(aliyun r-kvstore describe-slow-logs \
  --InstanceId "$INSTANCE_ID" \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output cols=TotalCount rows=TotalCount 2>/dev/null || echo "0")
echo "[3/5] Slow Logs (1h): $SLOW_COUNT"

# 4. Backup check
BACKUP_STATUS=$(aliyun r-kvstore describe-backups \
  --InstanceId "$INSTANCE_ID" \
  --PageSize 1 \
  --output cols=BackupStatus rows=Backups.Backup[0].BackupStatus 2>/dev/null || echo "N/A")
echo "[4/5] Last Backup: $BACKUP_STATUS"
[ "$BACKUP_STATUS" = "Success" ] && SCORE=$((SCORE + 10))

# 5. Whitelist check
WHITELIST=$(aliyun r-kvstore describe-security-ips \
  --InstanceId "$INSTANCE_ID" \
  --output cols=SecurityIpList rows=SecurityIpGroups.SecurityIpGroup[0].SecurityIpList 2>/dev/null || echo "N/A")
echo "[5/5] Whitelist: $WHITELIST"

echo ""
echo "=== Inspection Score: $SCORE/100 ==="
if [ "$SCORE" -ge 80 ]; then
  echo "Status: HEALTHY"
elif [ "$SCORE" -ge 60 ]; then
  echo "Status: WARNING - Review recommended"
else
  echo "Status: CRITICAL - Immediate action required"
fi
```

## Output Format

```json
{
  "inspection_time": "2026-05-14T10:00:00Z",
  "resource_type": "redis",
  "resource_id": "r-bp1zxszhcgatnx****",
  "overall_score": 85,
  "dimensions": [
    {"name": "实例状态", "score": 100, "status": "healthy"},
    {"name": "CPU使用率", "score": 80, "status": "warning", "value": "75%"},
    {"name": "内存使用率", "score": 60, "status": "critical", "value": "92%"},
    {"name": "连接使用率", "score": 90, "status": "healthy", "value": "45%"},
    {"name": "延迟", "score": 100, "status": "healthy", "value": "2ms"},
    {"name": "备份状态", "score": 100, "status": "healthy"}
  ],
  "recommendations": [
    "内存使用率92%超过严重阈值，建议扩容或优化数据",
    "CPU使用率75%超过警告阈值，建议检查慢查询"
  ]
}
```