# API & SDK Usage — Alibaba Cloud Simple Log Service (SLS)

## API Overview

Alibaba Cloud **Simple Log Service (SLS)** provides a comprehensive REST API for
log management operations. This reference covers API endpoints, authentication,
and the Go SDK fallback pattern.

**API version:** `2020-12-30` (current stable)

**Endpoint pattern:** `{project}.{region}.log.aliyuncs.com`

**Authentication:** RAM AK/SK with appropriate permissions

## Endpoint Reference

### Mainland China Regions

| Region | Endpoint |
|--------|----------|
| cn-hangzhou | `{project}.cn-hangzhou.log.aliyuncs.com` |
| cn-shanghai | `{project}.cn-shanghai.log.aliyuncs.com` |
| cn-beijing | `{project}.cn-beijing.log.aliyuncs.com` |
| cn-shenzhen | `{project}.cn-shenzhen.log.aliyuncs.com` |
| cn-heyuan | `{project}.cn-heyuan.log.aliyuncs.com` |

### International Regions

| Region | Endpoint |
|--------|----------|
| us-west-1 | `{project}.us-west-1.log.aliyuncs.com` |
| us-east-1 | `{project}.us-east-1.log.aliyuncs.com` |
| ap-southeast-1 | `{project}.ap-southeast-1.log.aliyuncs.com` |
| ap-southeast-3 | `{project}.ap-southeast-3.log.aliyuncs.com` |
| eu-central-1 | `{project}.eu-central-1.log.aliyuncs.com` |

## Operations Map

| Operation | API Path | Method | Description |
|-----------|----------|--------|-------------|
| CreateProject | `/` | POST | Create SLS project |
| GetProject | `/` | GET | Query project info |
| DeleteProject | `/` | DELETE | Delete project |
| CreateLogStore | `/logstores` | POST | Create logstore |
| GetLogStore | `/logstores/{logstore}` | GET | Query logstore |
| UpdateLogStore | `/logstores/{logstore}` | PUT | Update logstore |
| DeleteLogStore | `/logstores/{logstore}` | DELETE | Delete logstore |
| ListLogStores | `/logstores` | GET | List all logstores |
| CreateIndex | `/logstores/{logstore}/index` | POST | Create index |
| GetIndex | `/logstores/{logstore}/index` | GET | Query index |
| DeleteIndex | `/logstores/{logstore}/index` | DELETE | Delete index |
| GetLogs | `/logstores/{logstore}/logs` | GET | Query logs |
| GetHistograms | `/logstores/{logstore}/histograms` | GET | Get log histograms |
| CreateAlert | `/alerts` | POST | Create alert rule |
| ListAlerts | `/alerts` | GET | List alert rules |
| GetAlert | `/alerts/{alertName}` | GET | Query alert rule |
| UpdateAlert | `/alerts/{alertName}` | PUT | Update alert rule |
| DeleteAlert | `/alerts/{alertName}` | DELETE | Delete alert rule |
| CreateDashboard | `/dashboards` | POST | Create dashboard |
| ListDashboards | `/dashboards` | GET | List dashboards |
| GetDashboard | `/dashboards/{dashboardName}` | GET | Query dashboard |
| UpdateDashboard | `/dashboards/{dashboardName}` | PUT | Update dashboard |
| DeleteDashboard | `/dashboards/{dashboardName}` | DELETE | Delete dashboard |
| CreateConsumerGroup | `/logstores/{logstore}/consumergroups` | POST | Create consumer group |
| ConsumerGroupHeartBeat | `/logstores/{logstore}/consumergroups/{consumerGroup}?type=heartbeat` | POST | Consumer heartbeat |
| ConsumerGroupUpdateCheckPoint | `/logstores/{logstore}/consumergroups/{consumerGroup}?type=checkpoint` | POST | Update checkpoint |

## Common Headers

| Header | Value | Description |
|--------|-------|-------------|
| `x-log-apiversion` | `0.9.0` | API version |
| `x-log-bodyrawsize` | integer | Request body size |
| `Content-Type` | `application/json` | Request format |
| `x-log-compress-type` | `gzip` | Compression (optional) |

## Request/Response Patterns

### Project Operations

**CreateProject:**
```json
POST /
{
  "project": "my-project",
  "description": "Log Service project",
  "region": "cn-hangzhou"
}
```

**Response:**
```json
{
  "project": {
    "projectName": "my-project",
    "description": "Log Service project",
    "region": "cn-hangzhou",
    "owner": "1234567890",
    "createTime": 1625140800,
    "lastModifyTime": 1625140800
  }
}
```

### Logstore Operations

**CreateLogStore:**
```json
POST /logstores
{
  "logstore": "my-logstore",
  "ttl": 30,
  "shardCount": 2,
  "enableTracking": false,
  "appendMeta": true,
  "autoSplit": true,
  "maxSplitShard": 64,
  "preserve": false
}
```

**GetLogStore Response:**
```json
{
  "logstore": "my-logstore",
  "ttl": 30,
  "shardCount": 2,
  "enableTracking": false,
  "appendMeta": true,
  "autoSplit": true,
  "maxSplitShard": 64,
  "createTime": 1625140800,
  "lastModifyTime": 1625140800
}
```

### Index Operations

**CreateIndex:**
```json
POST /logstores/{logstore}/index
{
  "fullTextIndex": {
    "caseSensitive": false,
    "includeChinese": true,
    "token": ["@", " ", ","]
  },
  "keys": {
    "level": {
      "type": "text",
      "token": ["@"],
      "caseSensitive": false,
      "includeChinese": true
    },
    "message": {
      "type": "text",
      "token": ["@", " "],
      "caseSensitive": false,
      "includeChinese": true
    }
  }
}
```

### Log Query Operations

**GetLogs Request:**
```
GET /logstores/{logstore}/logs?from=1625140800&to=1625227200&query=level:ERROR&line=100&offset=0
```

**GetLogs Response:**
```json
{
  "count": 1500,
  "logs": [
    {
      "__time__": 1625140800,
      "__topic__": "",
      "__source__": "10.0.0.1",
      "level": "ERROR",
      "message": "Connection timeout",
      "stacktrace": "..."
    }
  ]
}
```

### Alert Operations

**CreateAlert:**
```json
POST /alerts
{
  "alertName": "error-alert",
  "displayName": "Error Alert",
  "description": "Alert on error logs",
  "type": "alert",
  "schedule": {
    "type": "FixedRate",
    "interval": "1m"
  },
  "configuration": {
    "query": "level:ERROR",
    "chartQuery": "level:ERROR | select count(*) as cnt",
    "condition": {
      "condition": ">",
      "threshold": 10
    },
    "dashboard": "my-dashboard"
  },
  "notification": {
    "notificationList": [
      {
        "type": "IM",
        "id": "my-im-group"
      }
    ]
  }
}
```

### Dashboard Operations

**CreateDashboard:**
```json
POST /dashboards
{
  "dashboardName": "my-dashboard",
  "displayName": "My Dashboard",
  "description": "Operational dashboard",
  "charts": [
    {
      "title": "Error Count",
      "type": "line",
      "logstore": "my-logstore",
      "query": "level:ERROR | select count(*) as cnt",
      "xAxis": {
        "type": "time"
      },
      "yAxis": {
        "type": "value"
      }
    }
  ]
}
```

## Go SDK Fallback

For operations not supported by the `aliyun sls` CLI, use the Go SDK directly.

### Dependency

```go
go get github.com/alibabacloud-go/sls-20201230/v4/client
```

### Credential Setup

```go
import (
    "github.com/alibabacloud-go/credentials"
)

func NewSLSClient(region string) (*sls.Client, error) {
    config := credentials.NewConfig().
        WithAccessKeyId(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")).
        WithAccessKeySecret(os.Getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")).
        WithType("access_key")

    credential, err := credentials.NewCredential(config)
    if err != nil {
        return nil, err
    }

    cli, err := sls.NewClient(region, "", credential, nil)
    if err != nil {
        return nil, err
    }

    return cli, nil
}
```

### Example Operations

**Create Project:**
```go
func CreateProject(cli *sls.Client, projectName, description string) error {
    req := &sls.CreateProjectRequest{
        Project:     projectName,
        Description: description,
    }

    _, err := cli.CreateProject(req)
    return err
}
```

**Get Logs:**
```go
func GetLogs(cli *sls.Client, logstore, query string, from, to int64) (*sls.GetLogsResponse, error) {
    req := &sls.GetLogsRequest{
        Logstore: logstore,
        Query:    query,
        From:     from,
        To:       to,
        Line:     100,
        Offset:   0,
    }

    return cli.GetLogs(req)
}
```

## Authentication & Permissions

### Required RAM Permissions

| Operation | RAM Action |
|-----------|------------|
| CreateProject | `log:CreateProject` |
| GetProject | `log:GetProject` |
| DeleteProject | `log:DeleteProject` |
| CreateLogStore | `log:CreateLogStore` |
| GetLogStore | `log:GetLogStore` |
| DeleteLogStore | `log:DeleteLogStore` |
| CreateIndex | `log:CreateIndex` |
| GetIndex | `log:GetIndex` |
| DeleteIndex | `log:DeleteIndex` |
| GetLogs | `log:GetLogs` |
| CreateAlert | `log:CreateAlert` |
| DeleteAlert | `log:DeleteAlert` |
| CreateDashboard | `log:CreateDashboard` |
| DeleteDashboard | `log:DeleteDashboard` |

### Example RAM Policy

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "log:CreateProject",
        "log:GetProject",
        "log:DeleteProject",
        "log:CreateLogStore",
        "log:GetLogStore",
        "log:DeleteLogStore",
        "log:CreateIndex",
        "log:GetIndex",
        "log:DeleteIndex",
        "log:GetLogs",
        "log:CreateAlert",
        "log:DeleteAlert",
        "log:CreateDashboard",
        "log:DeleteDashboard"
      ],
      "Resource": [
        "acs:log:*:*:project/*"
      ]
    }
  ]
}
```

## Rate Limits

| Operation | QPS Limit | Notes |
|-----------|-----------|-------|
| GetLogs | 500 | Per logstore |
| GetHistograms | 500 | Per logstore |
| Write | 1000 | Per shard |
| Alert evaluation | 100 | Per project |
| Dashboard queries | 100 | Per project |

## Error Handling

| HTTP Code | Error | Action |
|-----------|-------|--------|
| 400 | InvalidParameter | Check request parameters |
| 401 | Unauthorized | Check credentials |
| 403 | Forbidden.NoPermission | Add RAM permissions |
| 404 | NotFound | Resource doesn't exist |
| 409 | AlreadyExists | Resource already exists |
| 429 | Throttling | Backoff and retry |
| 500 | InternalError | Retry with backoff |
| 503 | ServiceUnavailable | Check status page |

## See Also

- [SLS OpenAPI Reference](https://help.aliyun.com/zh/sls/developer-reference/api-overview)
- [SLS Best Practices](https://help.aliyun.com/zh/sls/developer-reference/best-practices-for-log-service)
- [Go SDK Documentation](https://github.com/alibabacloud-go/sls-20201230)
