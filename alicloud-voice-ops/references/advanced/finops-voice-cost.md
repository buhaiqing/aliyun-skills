# Alibaba Cloud Voice Messaging Service FinOps Guide

## Cost Structure

### Pricing Models
1. **Pay-As-You-Go**: Pay per successful call
2. **Package Plans**: Pre-purchased call packages with discounts
3. **Dedicated Number Fees**: Monthly fees for dedicated caller IDs

### Key Cost Factors
| Factor | Description |
|--------|-------------|
| **Call Volume** | Number of successful calls (answered calls count towards cost) |
| **Call Duration** | Longer calls incur higher fees |
| **Dedicated Numbers** | Monthly fees for real numbers used as caller IDs |
| **Service Instances** | Fees for dedicated service instances |
| **Storage** | Storage fees for recorded voice files |

## Cost Optimization

### 1. Optimize Call Volume
- Use batch operations to reduce API calls and fees
- Implement retries only for valid cases, avoid unnecessary calls
- Filter invalid phone numbers before sending

### 2. Reduce Call Duration
- Use shorter voice files for notifications
- Use text-to-speech for dynamic content instead of pre-recorded files
- Limit playback attempts to 1-2 times unless required

### 3. Optimize Dedicated Resources
- Delete unused dedicated numbers and service instances
- Use shared mode for low-volume applications
- Right-size service instances based on usage

### 4. Storage Optimization
- Delete old voice recordings after 30 days
- Use low-cost storage for archived recordings

## Cost Monitoring

### CloudMonitor Cost Metrics
| Metric | Description |
|--------|-------------|
| `TotalCost` | Total monthly cost for voice service |
| `CallCost` | Cost from voice calls |
| `NumberCost` | Cost from dedicated numbers |
| `InstanceCost` | Cost from service instances |

### Cost Reports
1. Navigate to [Billing Console](https://billing.console.aliyun.com/)
2. Select **Cost Management** > **Cost Analysis**
3. Filter by product **Voice Messaging Service**
4. Export reports for monthly budgeting

## Budget Alerts

Set up budget alerts to avoid unexpected costs:
1. Go to [Billing Budget Management](https://billing.console.aliyun.com/budget)
2. Create a budget for voice messaging service
3. Set alerts for 80%, 100%, and 120% of budget
4. Receive notifications via email, Voice, or DingTalk

## Cost Saving Tips

1. **Use Free Trials**: Take advantage of Alibaba Cloud free tier for new accounts
2. **Purchase Packages**: Pre-purchased packages offer 20-50% discounts over pay-as-you-go
3. **Off-Peak Calling**: Schedule non-urgent notifications during off-peak hours
4. **Auto-Scaling**: Scale resources down during low-usage periods
5. **Filter Recipients**: Avoid sending calls to invalid or unsubscribed numbers

## Cost Optimization Checklist

✅ Audit usage reports monthly
✅ Delete unused resources
✅ Use batch operations
✅ Optimize call duration
✅ Use shared mode when possible
✅ Purchase pre-paid packages for steady usage
✅ Set up budget alerts
