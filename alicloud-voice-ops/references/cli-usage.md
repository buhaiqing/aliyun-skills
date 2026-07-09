# CLI — Alibaba Cloud Voice Service (`aliyun dyvmsapi`)

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
| SingleCallByVoice | yes | Single voice notification with audio file |
| SingleCallByTts | yes | Single TTS voice notification |
| BatchSendVoice | yes | Batch voice task creation |
| QueryCallDetails | yes | Query call detail records |
| QueryCallStatistics | yes | Query call statistics |
| AddVoiceSign | yes | Add voice signature |
| QueryVoiceSign | yes | Query voice signature status |
| DeleteVoiceSign | yes | Delete voice signature |
| ModifyVoiceSign | yes | Modify voice signature |
| AddVoiceTemplate | yes | Add voice template |
| QueryVoiceTemplate | yes | Query voice template status |
| DeleteVoiceTemplate | yes | Delete voice template |
| ModifyVoiceTemplate | yes | Modify voice template |

> Voice Service is fully supported by the `aliyun` CLI. No SDK-only operations for basic CRUD.

## Command Map

### Voice Sending Operations

```bash
# Send single voice notification with audio file
aliyun dyvmsapi SingleCallByVoice \
  --CalledNumber "13800138000" \
  --VoiceCode "123456" \
  --ShowNumber "4008123123"

# Send single TTS voice notification
aliyun dyvmsapi SingleCallByTts \
  --CalledNumber "13800138000" \
  --TtsCode "TTS_123456789" \
  --TtsParam '{"product":"Alibaba Cloud"}' \
  --ShowNumber "4008123123"

# Send batch voice tasks
aliyun dyvmsapi BatchSendVoice \
  --CalledNumbers '["13800138000","13800138001"]' \
  --VoiceCode "123456" \
  --VoiceSign "阿里云" \
  --ShowNumber "4008123123"
```

### Voice Signature Operations

```bash
# Add voice signature
aliyun dyvmsapi AddVoiceSign \
  --SignName "阿里云" \
  --SignSource "企业官网" \
  --FileList '["file://./voice_sign.png"]'

# Query voice signature status
aliyun dyvmsapi QueryVoiceSign --SignName "阿里云"

# Delete voice signature
aliyun dyvmsapi DeleteVoiceSign --SignName "阿里云"

# Modify voice signature
aliyun dyvmsapi ModifyVoiceSign \
  --SignName "阿里云" \
  --SignSource "企业官网" \
  --FileList '["file://./updated_voice_sign.png"]'
```

### Voice Template Operations

```bash
# Add voice template
aliyun dyvmsapi AddVoiceTemplate \
  --TemplateName "验证码模板" \
  --TemplateType "0" \
  --TemplateContent "您的验证码是{{code}}，请在5分钟内使用。" \
  --Remark "用于用户身份验证"

# Query voice template status
aliyun dyvmsapi QueryVoiceTemplate --TemplateCode "VT_123456789"

# Delete voice template
aliyun dyvmsapi DeleteVoiceTemplate --TemplateCode "VT_123456789"

# Modify voice template
aliyun dyvmsapi ModifyVoiceTemplate \
  --TemplateCode "VT_123456789" \
  --TemplateName "更新后的验证码模板" \
  --TemplateType "0" \
  --TemplateContent "您的验证码是{{code}}，请在10分钟内使用。" \
  --Remark "更新后的验证模板"
```

### Query Operations

```bash
# Query call details
aliyun dyvmsapi QueryCallDetails \
  --CalledNumber "13800138000" \
  --CallTime "2026-06-15"

# Query call statistics
aliyun dyvmsapi QueryCallStatistics \
  --StartDate "2026-06-08" \
  --EndDate "2026-06-15"
```