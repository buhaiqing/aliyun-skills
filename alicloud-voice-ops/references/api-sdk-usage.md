# API & SDK — Alibaba Cloud Voice Service

## OpenAPI

- **Service**: Dysmsapi
- **API Version**: 2017-05-25
- **Base Endpoint**: `dyvmsapi.aliyuncs.com` (regional endpoints also available)
- **Official Docs**: https://www.alibabacloud.com/help/en/sms
- **OpenAPI Explorer**: https://api.aliyun.com/

## SDK Operations Map

| Goal | API OperationId | SDK Method | CLI Command |
|------|-----------------|------------|-------------|
| Send single Voice call | `SingleCallByVoice` | `SingleCallByVoice()` | `aliyun dyvmsapi SingleCallByVoice` |
| Send single TTS Voice call | `SingleCallByTts` | `SingleCallByTts()` | `aliyun dyvmsapi SingleCallByTts` |
| Send batch Voice calls | `BatchCallByVoice` | `BatchCallByVoice()` | `aliyun dyvmsapi BatchCallByVoice` |
| Query call details | `QueryCallDetailByCallId` | `QueryCallDetailByCallId()` | `aliyun dyvmsapi QueryCallDetailByCallId` |
| Query batch task details | `QueryCallTaskDetail` | `QueryCallTaskDetail()` | `aliyun dyvmsapi QueryCallTaskDetail` |
| Query voice file audit info | `QueryVoiceFileAuditInfo` | `QueryVoiceFileAuditInfo()` | `aliyun dyvmsapi QueryVoiceFileAuditInfo` |
| Add voice signature | `AddVoiceSign` | `AddVoiceSign()` | `aliyun dyvmsapi AddVoiceSign` |
| Query voice signature | `QueryVoiceSign` | `QueryVoiceSign()` | `aliyun dyvmsapi QueryVoiceSign` |
| Delete voice signature | `DeleteVoiceSign` | `DeleteVoiceSign()` | `aliyun dyvmsapi DeleteVoiceSign` |
| Modify voice signature | `ModifyVoiceSign` | `ModifyVoiceSign()` | `aliyun dyvmsapi ModifyVoiceSign` |
| Add voice template | `AddVoiceTemplate` | `AddVoiceTemplate()` | `aliyun dyvmsapi AddVoiceTemplate` |
| Query voice template | `QueryVoiceTemplate` | `QueryVoiceTemplate()` | `aliyun dyvmsapi QueryVoiceTemplate` |
| Delete voice template | `DeleteVoiceTemplate` | `DeleteVoiceTemplate()` | `aliyun dyvmsapi DeleteVoiceTemplate` |
| Modify voice template | `ModifyVoiceTemplate` | `ModifyVoiceTemplate()` | `aliyun dyvmsapi ModifyVoiceTemplate` |

## SDK Package

```bash
go get github.com/alibabacloud-go/dyvmsapi-20170525/v3/client
```

## Request / Response Notes

### SingleCallByVoice
- **Required**: `CalledNumber`, `VoiceCode`, `ShowNumber`
- **Optional**: `CalledShowNumber`, `Volume`, `Speed`, `PlayTimes`
- **Response**: `Code`, `Message`, `RequestId`, `CallId`
- **Idempotency**: Client `OutId` prevents duplicate calls

### SingleCallByTts
- **Required**: `CalledNumber`, `TtsCode`, `ShowNumber`
- **Optional**: `TtsParam` (JSON string), `OutId` (tracking ID)
- **Response**: `Code`, `Message`, `RequestId`, `CallId`

### BatchCallByVoice
- **Required**: `CalledNumbers` (JSON array), `VoiceCode`, `VoiceSign`, `ShowNumber`
- **All phone numbers must be in E.164 format**
- **Response**: `Code`, `Message`, `RequestId`, `TaskId`

### QueryCallDetailByCallId
- **Required**: `CallId`
- **Response**: `CallDetails` array with call status, duration, etc.

### QueryCallTaskDetail
- **Required**: `TaskId`
- **Response**: `TaskDetail` with batch task status, success count, etc.

### QueryVoiceFileAuditInfo
- **Required**: `FileName`
- **Response**: `AuditStatus`, `FileName`, `CreateTime`

### AddVoiceSign
- **Required**: `SignName`, `SignSource`
- **Optional**: `FileList` (JSON array of file URLs)
- **Response**: `Code`, `Message`, `RequestId`

### QueryVoiceSign
- **Required**: `SignName`
- **Response**: `SignName`, `SignStatus`, `AuditStatus`, `CreateDate`, `Reason`

### DeleteVoiceSign
- **Required**: `SignName`
- **Response**: `Code`, `Message`, `RequestId`

### ModifyVoiceSign
- **Required**: `SignName`, `SignSource`
- **Optional**: `FileList` (JSON array of file URLs)
- **Response**: `Code`, `Message`, `RequestId`

### AddVoiceTemplate
- **Required**: `TemplateName`, `TemplateType`, `TemplateContent`
- **Optional**: `Remark`
- **Response**: `Code`, `Message`, `RequestId`, `TemplateCode`

### QueryVoiceTemplate
- **Required**: `TemplateCode`
- **Response**: `TemplateCode`, `TemplateName`, `TemplateType`, `TemplateContent`, `TemplateStatus`, `AuditStatus`, `CreateDate`, `Reason`

### DeleteVoiceTemplate
- **Required**: `TemplateCode`
- **Response**: `Code`, `Message`, `RequestId`

### ModifyVoiceTemplate
- **Required**: `TemplateCode`, `TemplateName`, `TemplateType`, `TemplateContent`
- **Optional**: `Remark`
- **Response**: `Code`, `Message`, `RequestId`
