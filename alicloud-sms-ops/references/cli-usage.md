# CLI — Alibaba Cloud SMS Service (`aliyun dysmsapi`)

## Install and Config

- Install: see [Alibaba Cloud CLI](https://github.com/aliyun/aliyun-cli)
- **CRITICAL Credentials:** The `aliyun` CLI reads from env vars `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET` OR `~/.aliyun/config.json` (JSON format).
- For sandbox environments, set env vars directly (preferred) or use `--config-path`.

## Conventions (agent execution)

- Output is **JSON by default** — NO `--output json` needed for plain JSON
- Use `--output cols=...,rows=...` for JMESPath tabular extraction
- `--no-interactive` does NOT exist in `aliyun` CLI — all commands are non-interactive by default
- Document **exact** JSON paths after verifying with a real invocation

## CLI vs API Coverage Gap

| Operation (API / SDK) | Available via `aliyun`? | Notes |
|------------------------|---------------------|-------|
| SendSms | yes | Full support |
| SendBatchSms | yes | Full support |
| QuerySendDetails | yes | Full support with pagination |
| QuerySendStatistics | yes | Full support |
| AddSmsSign | yes | Full support |
| QuerySmsSign | yes | Full support |
| DeleteSmsSign | yes | Full support |
| ModifySmsSign | yes | Full support |
| AddSmsTemplate | yes | Full support |
| QuerySmsTemplate | yes | Full support |
| DeleteSmsTemplate | yes | Full support |
| ModifySmsTemplate | yes | Full support |

> SMS Service is fully supported by the `aliyun` CLI. No SDK-only operations for basic CRUD.

## Command Map

### SMS Sending Operations

```bash
# Send single SMS
aliyun dysmsapi SendSms \
  --PhoneNumbers "13800138000" \
  --SignName "阿里云" \
  --TemplateCode "SMS_123456789" \
  --TemplateParam '{"code":"1234"}'

# Send batch SMS (up to 100 numbers)
aliyun dysmsapi SendBatchSms \
  --PhoneNumberJson "{{user.phone_numbers_json}}" \
  --SignNameJson "{{user.sign_names_json}}" \
  --TemplateCode "{{user.template_code}}" \
  --TemplateParamJson "{{user.template_params_json}}"

# Send with OutId tracking
aliyun dysmsapi SendSms \
  --PhoneNumbers "13800138000" \
  --SignName "阿里云" \
  --TemplateCode "SMS_123456789" \
  --TemplateParam '{"code":"1234"}' \
  --OutId "order_12345"
```

### Query Operations

```bash
# Query send details for specific phone and date
aliyun dysmsapi QuerySendDetails \
  --PhoneNumbers "13800138000" \
  --SendDate "$(date +%Y-%m-%d)" \
  --PageSize 10 \
  --Page 1

# Query daily statistics for last 7 days
aliyun dysmsapi QuerySendStatistics \
  --StartDate "$(date -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d)" \
  --EndDate "$(date +%Y-%m-%d)"
```

### Signature Operations

```bash
# Add SMS signature
aliyun dysmsapi AddSmsSign \
  --SignName "我的签名" \
  --SignSource 0

# Query signature status
aliyun dysmsapi QuerySmsSign --SignName "我的签名"

# Delete signature (requires confirmation)
aliyun dysmsapi DeleteSmsSign --SignName "我的签名"

# Modify signature
aliyun dysmsapi ModifySmsSign \
  --SignName "我的签名" \
  --SignSource 0
```

### Template Operations

```bash
# Add SMS template
aliyun dysmsapi AddSmsTemplate \
  --TemplateName "验证码" \
  --TemplateType 0 \
  --TemplateContent "您的验证码是${code}，5分钟内有效" \
  --Remark "登录验证码"

# Query template status
aliyun dysmsapi QuerySmsTemplate --TemplateCode "SMS_123456789"

# Delete template (requires confirmation)
aliyun dysmsapi DeleteSmsTemplate --TemplateCode "SMS_123456789"

# Modify template
aliyun dysmsapi ModifySmsTemplate \
  --TemplateCode "SMS_123456789" \
  --TemplateName "验证码" \
  --TemplateType 0 \
  --TemplateContent "您的验证码是${code}，5分钟内有效" \
  --Remark "登录验证码"
```

### JMESPath Extraction Examples

```bash
# Extract send status from QuerySendDetails
aliyun dysmsapi QuerySendDetails \
  --PhoneNumbers "13800138000" \
  --SendDate "2026-06-15" \
  --output cols=SendStatus,SendTime,Receiver rows=SmsSendDetailDTOs.SmsSendDetailDTO[].{SendStatus,SendTime,Receiver}

# Extract statistics
aliyun dysmsapi QuerySendStatistics \
  --StartDate "2026-06-08" \
  --EndDate "2026-06-15" \
  --output cols=SmsDate,SmsSendCount,SmsSuccessCount rows=SmsSendStatDTOs.SmsSendStatDTO[].{SmsDate,SmsSendCount,SmsSuccessCount}
```
