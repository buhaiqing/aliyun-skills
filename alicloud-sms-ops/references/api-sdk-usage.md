# API & SDK — Alibaba Cloud SMS Service

## OpenAPI

- **Service**: Dysmsapi
- **API Version**: 2017-05-25
- **Base Endpoint**: `dysmsapi.aliyuncs.com` (regional endpoints also available)
- **Official Docs**: https://www.alibabacloud.com/help/en/sms
- **OpenAPI Explorer**: https://api.aliyun.com/

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Send single SMS | `SendSms` | `SendSms()` | `aliyun dysmsapi SendSms` |
| Send batch SMS | `SendBatchSms` | `SendBatchSms()` | `aliyun dysmsapi SendBatchSms` |
| Query send details | `QuerySendDetails` | `QuerySendDetails()` | `aliyun dysmsapi QuerySendDetails` |
| Query send statistics | `QuerySendStatistics` | `QuerySendStatistics()` | `aliyun dysmsapi QuerySendStatistics` |
| Add signature | `AddSmsSign` | `AddSmsSign()` | `aliyun dysmsapi AddSmsSign` |
| Query signature | `QuerySmsSign` | `QuerySmsSign()` | `aliyun dysmsapi QuerySmsSign` |
| Delete signature | `DeleteSmsSign` | `DeleteSmsSign()` | `aliyun dysmsapi DeleteSmsSign` |
| Modify signature | `ModifySmsSign` | `ModifySmsSign()` | `aliyun dysmsapi ModifySmsSign` |
| Add template | `AddSmsTemplate` | `AddSmsTemplate()` | `aliyun dysmsapi AddSmsTemplate` |
| Query template | `QuerySmsTemplate` | `QuerySmsTemplate()` | `aliyun dysmsapi QuerySmsTemplate` |
| Delete template | `DeleteSmsTemplate` | `DeleteSmsTemplate()` | `aliyun dysmsapi DeleteSmsTemplate` |
| Modify template | `ModifySmsTemplate` | `ModifySmsTemplate()` | `aliyun dysmsapi ModifySmsTemplate` |

## SDK Package

```bash
go get github.com/alibabacloud-go/dysmsapi-20170525/v3/client
```

## Request / Response Notes

### SendSms
- **Required**: `PhoneNumbers`, `SignName`, `TemplateCode`
- **Optional**: `TemplateParam` (JSON string), `OutId` (tracking ID)
- **Response**: `Code`, `Message`, `RequestId`, `BizId`
- **Idempotency**: Client `OutId` prevents duplicate sends

### SendBatchSms
- **Required**: `PhoneNumberJson`, `SignNameJson`, `TemplateCode`, `TemplateParamJson`
- **All are JSON arrays** — must match in length
- **Response**: `Code`, `Message`, `RequestId`, `BizId`

### QuerySendDetails
- **Required**: `PhoneNumbers`, `SendDate`
- **Pagination**: `Page`, `PageSize` (default 10, max 100)
- **Response**: `SmsSendDetailDTOs.SmsSendDetailDTO[]` array

### QuerySendStatistics
- **Required**: `StartDate`, `EndDate`
- **Response**: `SmsSendStatDTOs.SmsSendStatDTO[]` array

### AddSmsSign
- **Required**: `SignName`, `SignSource`
- **Optional**: `MoreData` (file list)
- **Response**: `Code`, `Message`, `RequestId`

### QuerySmsSign
- **Required**: `SignName`
- **Response**: `SignName`, `SignStatus`, `AuditStatus`, `CreateDate`, `Reason`

### DeleteSmsSign
- **Required**: `SignName`
- **Response**: `Code`, `Message`, `RequestId`

### ModifySmsSign
- **Required**: `SignName`, `SignSource`
- **Optional**: `MoreData` (file list)
- **Response**: `Code`, `Message`, `RequestId`

### AddSmsTemplate
- **Required**: `TemplateName`, `TemplateType`, `TemplateContent`
- **Optional**: `Remark`
- **Response**: `Code`, `Message`, `RequestId`, `TemplateCode`

### QuerySmsTemplate
- **Required**: `TemplateCode`
- **Response**: `TemplateCode`, `TemplateName`, `TemplateType`, `TemplateContent`, `TemplateStatus`, `AuditStatus`, `CreateDate`, `Reason`

### DeleteSmsTemplate
- **Required**: `TemplateCode`
- **Response**: `Code`, `Message`, `RequestId`

### ModifySmsTemplate
- **Required**: `TemplateCode`, `TemplateName`, `TemplateType`, `TemplateContent`
- **Optional**: `Remark`
- **Response**: `Code`, `Message`, `RequestId`
