# Alibaba Cloud Voice Messaging Service Monitoring

## CloudMonitor Metrics

Voice Messaging Service provides these metrics in CloudMonitor:

### Call Metrics
| Metric | Description | Unit |
|--------|-------------|------|
| `CallTotalCount` | Total number of calls | Count |
| `CallSuccessCount` | Number of successful calls | Count |
| `CallFailureCount` | Number of failed calls | Count |
| `CallAnsweredCount` | Number of calls answered by recipients | Count |
| `CallDuration` | Average call duration | Seconds |

### Task Metrics
| Metric | Description | Unit |
|--------|-------------|------|
| `TaskTotalCount` | Total number of batch tasks | Count |
| `TaskSuccessCount` | Number of successful tasks | Count |
| `TaskFailureCount` | Number of failed tasks | Count |

## Default Dashboards

Alibaba Cloud provides a pre-built dashboard for Voice Messaging Service:
1. Navigate to [CloudMonitor Console](https://cms.console.aliyun.com/)
2. Select **Dashboard** > **Custom Dashboard** > **Voice Messaging Service**
3. View metrics for:
   - Call volume over time
   - Success rate
   - Top failed error codes
   - Recipient distribution

## Alarms & Alerting

### Recommended Alarm Rules

| Metric | Threshold | Notification Frequency |
|--------|-----------|-----------------------|
| `CallSuccessRate` | < 95% | Every 5 minutes |
| `CallFailureCount` | > 10 in 5 minutes | Every 5 minutes |
| `TaskFailureRate` | > 5% | Every 5 minutes |

### Configure Alarms

1. Go to [CloudMonitor Alarm Rules](https://cms.console.aliyun.com/alert/rule)
2. Click **Create Alarm Rule**
3. Select product **Voice Messaging Service**
4. Choose metrics to monitor
5. Set threshold and notification channels

## Logging

### API Logs
All API calls are logged in ActionTrail:
1. Navigate to [ActionTrail Console](https://actiontrail.console.aliyun.com/)
2. View logs for Dyvmsapi operations
3. Export logs to OSS or SLS for long-term storage

### Call Detail Logs
Call details including recording URLs are available via:
- `query-call-detail-by-call-id` API
- Voice Service Console > Call Records

## Performance Monitoring

Key performance metrics to track:
- **API Response Time**: < 500ms (target)
- **Call Setup Time**: < 3 seconds (target)
- **Recording Availability**: 99.9% uptime

## Troubleshooting Monitoring Issues

1. **Missing metrics**: Verify the region matches your service region
2. **Delayed data**: CloudMonitor metrics can take up to 5 minutes to appear
3. **No alarm notifications**: Check alarm rule configuration and contact group
