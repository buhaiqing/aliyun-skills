# Alibaba Cloud Voice Messaging Service Core Concepts

## Overview

Alibaba Cloud Voice Messaging Service (Dyvmsapi) provides short voice notification and verification call capabilities, including:
- **Voice Verification Calls**: Automated phone calls with pre-recorded or TTS-generated verification codes
- **Voice Notifications**: Automated phone calls to notify users of important events
- **Batch Voice Calls**: Bulk voice notifications to multiple phone numbers
- **Voice Signature Management**: Manage voice service signatures for authentication
- **Voice Template Management**: Manage voice message templates for consistent notifications

## Key Concepts

### Voice Signature
A signature is the identity credential used when sending voice messages. You must apply for and obtain approval for a voice signature before you can send voice messages.

### Voice Template
A template is the content framework for voice messages. You must create and obtain approval for a voice template before you can send voice messages.

### Call Status
- **0**: Calling in progress
- **1**: Call successful
- **2**: Call failed
- **3**: Call answered
- **4**: Call hung up

### Supported Regions

Voice Messaging Service is available in these Alibaba Cloud regions:
- **cn-hangzhou** (Hangzhou)
- **cn-shanghai** (Shanghai)
- **cn-beijing** (Beijing)
- **cn-shenzhen** (Shenzhen)
- **cn-qingdao** (Qingdao)
- **cn-zhangjiakou** (Zhangjiakou)
- **cn-huhehaote** (Hohhot)
- **cn-wulanchabu** (Ulan Qab)
- **ap-southeast-1** (Singapore)
- **ap-southeast-2** (Sydney)
- **ap-southeast-3** (Kuala Lumpur)
- **ap-southeast-5** (Jakarta)
- **ap-northeast-1** (Tokyo)
- **us-west-1** (Silicon Valley)
- **eu-central-1** (Frankfurt)

## Quota Limits

- Maximum batch call size: 100 numbers per request
- Maximum template content length: 500 characters
- Maximum verification code length: 8 digits
- Minimum interval between calls: 60 seconds per phone number

## Security Best Practices

- Use least-privilege RAM policies for voice service operations
- Never hardcode credentials in scripts or application code
- Validate phone numbers before sending calls
- Use signature verification to prevent spoofing