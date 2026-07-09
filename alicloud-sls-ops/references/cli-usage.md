# CLI Usage — Alibaba Cloud Simple Log Service (SLS)

## Overview

Alibaba Cloud **Simple Log Service (SLS)** provides a CLI via the `aliyun sls` command.
This reference covers CLI installation, command patterns, and usage examples.

**Important:** SLS CLI requires plugin installation and uses REST-style path patterns.

## Plugin Installation

### Install SLS CLI Plugin

```bash
# Install the SLS plugin (required)
aliyun plugin install --names aliyun-cli-sls
```

### Verify Installation

```bash
# Check if plugin is installed
aliyun sls --version
```

## Command Pattern

SLS CLI uses REST-style path patterns with HTTP methods:

```bash
# General pattern
aliyun sls <METHOD> <path> --header "x-log-apiversion=0.9.0" --body "..." --project <project>

# Method: GET, POST, PUT, DELETE
# Path: REST API path (e.g., /logstores, /logstores/{logstore}/logs)
```

### Common Headers

```bash
--header "x-log-apiversion=0.9.0"  # Required API version
--header "Content-Type: application/json"  # Optional, defaults to JSON
```

### Project Parameter

```bash
--project "my-project"  # SLS project name (required for most operations)
```

## CLI Command Map

### Project Operations

```bash
# Create project
aliyun sls POST / \
  --header "x-log-apiversion=0.9.0" \
  --body '{"project":"my-project","description":"Log Service project","region":"cn-hangzhou"}'

# Get project info
aliyun sls GET / \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"

# Delete project
aliyun sls DELETE / \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"
```

### Logstore Operations

```bash
# Create logstore
aliyun sls POST /logstores \
  --header "x-log-apiversion=0.9.0" \
  --body '{"logstore":"my-logstore","ttl":30,"shardCount":2}' \
  --project "my-project"

# Get logstore
aliyun sls GET /logstores/my-logstore \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"

# Update logstore
aliyun sls PUT /logstores/my-logstore \
  --header "x-log-apiversion=0.9.0" \
  --body '{"ttl":60}' \
  --project "my-project"

# Delete logstore
aliyun sls DELETE /logstores/my-logstore \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"

# List logstores
aliyun sls GET /logstores \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"
```

### Index Operations

```bash
# Create index
aliyun sls POST /logstores/my-logstore/index \
  --header "x-log-apiversion=0.9.0" \
  --body '{"fullTextIndex":{"caseSensitive":false,"includeChinese":true,"token":["@"," ", ","]}}' \
  --project "my-project"

# Get index
aliyun sls GET /logstores/my-logstore/index \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"

# Delete index
aliyun sls DELETE /logstores/my-logstore/index \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"
```

### Log Query Operations

```bash
# Get logs with SQL query
aliyun sls GET /logstores/my-logstore/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "from * | select __time__, __topic__, content limit 100" \
  --project "my-project"

# Get logs with time range
aliyun sls GET /logstores/my-logstore/logs \
  --header "x-log-apiversion=0.9.0" \
  --query "level:ERROR" \
  --from 1625140800 \
  --to 1625227200 \
  --line 100 \
  --offset 0 \
  --project "my-project"

# Get histograms
aliyun sls GET /logstores/my-logstore/histograms \
  --header "x-log-apiversion=0.9.0" \
  --query "level:ERROR" \
  --from 1625140800 \
  --to 1625227200 \
  --project "my-project"
```

### Alert Operations

```bash
# Create alert
aliyun sls POST /alerts \
  --header "x-log-apiversion=0.9.0" \
  --body '{"alertName":"error-alert","displayName":"Error Alert","description":"Alert on error logs","type":"alert","schedule":{"type":"FixedRate","interval":"1m"},"configuration":{"query":"level:ERROR","chartQuery":"level:ERROR | select count(*) as cnt","condition":{"condition":">","threshold":10}}}' \
  --project "my-project"

# List alerts
aliyun sls GET /alerts \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"

# Get alert
aliyun sls GET /alerts/error-alert \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"

# Update alert
aliyun sls PUT /alerts/error-alert \
  --header "x-log-apiversion=0.9.0" \
  --body '{"configuration":{"query":"level:ERROR OR level:FATAL"}}' \
  --project "my-project"

# Delete alert
aliyun sls DELETE /alerts/error-alert \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"
```

### Dashboard Operations

```bash
# Create dashboard
aliyun sls POST /dashboards \
  --header "x-log-apiversion=0.9.0" \
  --body '{"dashboardName":"my-dashboard","displayName":"My Dashboard","description":"Operational dashboard","charts":[{"title":"Error Count","type":"line","logstore":"my-logstore","query":"level:ERROR | select count(*) as cnt","xAxis":{"type":"time"},"yAxis":{"type":"value"}}]}' \
  --project "my-project"

# List dashboards
aliyun sls GET /dashboards \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"

# Get dashboard
aliyun sls GET /dashboards/my-dashboard \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"

# Delete dashboard
aliyun sls DELETE /dashboards/my-dashboard \
  --header "x-log-apiversion=0.9.0" \
  --project "my-project"
```

### Consumer Group Operations

```bash
# Create consumer group
aliyun sls POST /logstores/my-logstore/consumergroups \
  --header "x-log-apiversion=0.9.0" \
  --body '{"consumerGroup":"my-group","order":true,"timeout":300}' \
  --project "my-project"

# Consumer heartbeat
aliyun sls POST /logstores/my-logstore/consumergroups/my-group?type=heartbeat \
  --header "x-log-apiversion=0.9.0" \
  --body '{"consumerName":"consumer-1"}' \
  --project "my-project"

# Update checkpoint
aliyun sls POST /logstores/my-logstore/consumergroups/my-group?type=checkpoint \
  --header "x-log-apiversion=0.9.0" \
  --body '{"consumerName":"consumer-1","checkpoint":"1625140800"}' \
  --project "my-project"
```

## Output Parsing

### JSON Response

All CLI commands return JSON responses. Parse with `jq`:

```bash
# Get project name
aliyun sls GET / --header "x-log-apiversion=0.9.0" --project "my-project" | jq '.project.projectName'

# Get logstore count
aliyun sls GET /logstores --header "x-log-apiversion=0.9.0" --project "my-project" | jq '.logstores | length'

# Get log count
aliyun sls GET /logstores/my-logstore/logs --header "x-log-apiversion=0.9.0" --query "level:ERROR" --project "my-project" | jq '.count'
```

### Error Handling

```bash
# Check for errors
RESPONSE=$(aliyun sls GET /logstores/my-logstore --header "x-log-apiversion=0.9.0" --project "my-project" 2>&1)
if [ $? -ne 0 ]; then
  echo "Error: $RESPONSE"
  # Parse error code
  ERROR_CODE=$(echo "$RESPONSE" | jq -r '.code')
  case $ERROR_CODE in
    "ProjectNotFound") echo "Project not found" ;;
    "LogstoreNotFound") echo "Logstore not found" ;;
    *) echo "Unknown error" ;;
  esac
fi
```

## Common Flags

| Flag | Description | Example |
|------|-------------|---------|
| `--header` | HTTP header | `--header "x-log-apiversion=0.9.0"` |
| `--body` | Request body (JSON) | `--body '{"logstore":"test"}'` |
| `--project` | SLS project name | `--project "my-project"` |
| `--query` | SQL query | `--query "level:ERROR"` |
| `--from` | Start timestamp | `--from 1625140800` |
| `--to` | End timestamp | `--to 1625227200` |
| `--line` | Max results | `--line 100` |
| `--offset` | Result offset | `--offset 0` |

## Rate Limits

| Operation | QPS Limit | Notes |
|-----------|-----------|-------|
| GetLogs | 500 | Per logstore |
| GetHistograms | 500 | Per logstore |
| Write | 1000 | Per shard |
| Alert evaluation | 100 | Per project |

## Troubleshooting

### Plugin Not Found

```bash
# Error: Command "sls" not found
# Solution: Install plugin
aliyun plugin install --names aliyun-cli-sls
```

### Authentication Error

```bash
# Error: InvalidAccessKeyId
# Solution: Check credentials
echo $ALIBABA_CLOUD_ACCESS_KEY_ID
echo $ALIBABA_CLOUD_ACCESS_KEY_SECRET
```

### Rate Limiting

```bash
# Error: Throttling
# Solution: Add retry with backoff
for i in 1 2 3; do
  aliyun sls GET /logstores/my-logstore/logs --header "x-log-apiversion=0.9.0" --query "level:ERROR" --project "my-project" && break
  sleep $((2 ** i))
done
```

## See Also

- [SLS CLI Reference](https://help.aliyun.com/zh/sls/developer-reference/api-overview)
- [SLS Best Practices](https://help.aliyun.com/zh/sls/developer-reference/best-practices-for-log-service)
