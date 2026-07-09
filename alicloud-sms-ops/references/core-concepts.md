# Core Concepts — Alibaba Cloud SMS Service

## What is SMS Service?

Alibaba Cloud SMS Service (短信服务, Dysmsapi) provides short message service capabilities including single/batch SMS sending, signature and template management, delivery reports, and verification codes.

## Key Concepts

### SMS Signature (短信签名)
- Required for all SMS sending operations
- Must be approved before use (review typically 1-2 business days)
- Sources: verification code (0), marketing (1), notification (2), utility (3)
- Statuses: under review (0), approved (1), rejected (2)
- Must be unique across your account

### SMS Template (短信模板)
- Required for all SMS sending operations
- Must be approved before use
- Types: verification (0), marketing (1), notification (2), utility (3)
- Contains `${variable}` placeholders for dynamic content
- Max 500 characters per template

### SendSms (发送短信)
- Single SMS sending API
- Requires: PhoneNumbers, SignName, TemplateCode
- Optional: TemplateParam (JSON), OutId (tracking ID)
- Returns: BizId for delivery tracking

### SendBatchSms (批量发送)
- Batch SMS sending API (up to 100 numbers per call)
- Requires: PhoneNumberJson, SignNameJson, TemplateCode, TemplateParamJson
- Phone count must match parameter count

### QuerySendDetails (查询发送详情)
- Query delivery reports for specific phone/date
- Returns: SendStatus, SendTime, Receiver, Content, ErrCode, ErrMsg

### QuerySendStatistics (查询发送统计)
- Query daily sending statistics for date range
- Returns: SmsSendCount, SmsSuccessCount, SmsSpeed, SmsSuccessRate

## Send Status Codes

| Code | Status | Description |
|------|--------|-------------|
| 0 | 发送中 | Sending in progress |
| 1 | 发送失败 | Send failed |
| 2 | 发送成功 | Send successful |
| 3 | 已接受 | Accepted by carrier |
| 4 | 未知状态 | Unknown status |
| 5 | 等待发送 | Pending send |
| 6 | 发送失败(运营商) | Carrier rejection |

## Signature Status Codes

| Status | Meaning |
|--------|---------|
| 0 | 审核中 (Under review) |
| 1 | 审核通过 (Approved) |
| 2 | 审核失败 (Rejected) |

## Template Types

| Type | Name | Use Case |
|------|------|----------|
| 0 | 验证码 | Verification codes (login, registration) |
| 1 | 营销短信 | Marketing messages |
| 2 | 通知短信 | Notifications (order, delivery) |
| 3 | 短信工具 | Utility messages |

## Resource Dependencies

```
SMS Signature → Required for SendSms
SMS Template → Required for SendSms
SendSms → Produces BizId
BizId → Input for QuerySendDetails
```

## Important Notes

- Signatures and templates must be approved before use
- SMS content is审核通过 by Alibaba Cloud
- Rate limits apply per-second and per-day
- Phone numbers must be 11-digit Chinese mobile numbers
- Template parameters must match `${variable}` placeholders
- Delivery status is asynchronous; check via QuerySendDetails

## Cost Model

- Pay-per-SMS (based on destination and quantity)
- SMS packages available for bulk discounts
- Different pricing for verification vs marketing vs notification

## Rate Limits

- SendSms: 1 SMS per 100ms per signature
- SendBatchSms: 1 batch per second
- QuerySendDetails: 10 QPS
- QuerySendStatistics: 10 QPS

## Supported Regions

Alibaba Cloud SMS Service is available in the following regions:

| Region ID | Region Name |
|-----------|-------------|
| cn-hangzhou | China (Hangzhou) |
| cn-shanghai | China (Shanghai) |
| cn-beijing | China (Beijing) |
| cn-shenzhen | China (Shenzhen) |
| cn-qingdao | China (Qingdao) |
| cn-zhangjiakou | China (Zhangjiakou) |
| cn-huhehaote | China (Hohhot) |
| cn-wulumuqhi | China (Urumqi) |
| cn-chengdu | China (Chengdu) |
| cn-hongkong | China (Hong Kong) |
| ap-singapore | Singapore |
| ap-tokyo | Japan (Tokyo) |
| ap-seoul | South Korea (Seoul) |
| ap-sydney | Australia (Sydney) |
| ap-mumbai | India (Mumbai) |
| ap-jakarta | Indonesia (Jakarta) |
| eu-central-1 | Germany (Frankfurt) |
| eu-west-1 | UK (London) |
| us-west-1 | US (Silicon Valley) |
| us-east-1 | US (Virginia) |
| me-east-1 | UAE (Dubai) |
| ap-bangkok | Thailand (Bangkok) |
| ap-hanoi | Vietnam (Hanoi) |
| ap-kualalumpur | Malaysia (Kuala Lumpur) |
| sa-east-1 | Brazil (São Paulo) |
