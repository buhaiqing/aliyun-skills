# Troubleshooting Alibaba Cloud SMS Service

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `InvalidParameter` / 400 | Request failed validation | Align body with OpenAPI; check phone number format |
| `isv.SMS_SIGNATURE_ILLEGAL` | Signature not valid | Fix sign name format; ensure approved |
| `isv.SMS_TEMPLATE_ILLEGAL` | Template not valid | Fix template content; ensure approved |
| `isv.SMS_TEMPLATE_UNAPPROVED` | Template not approved | Wait for approval or resubmit |
| `isv.SMS_SIGNATURE_UNAPPROVED` | Signature not approved | Wait for approval or resubmit |
| `isv.SMS_SIGN_NAME_ILLEGAL` | Sign name format invalid | Use Chinese/English, 2-12 chars |
| `isv.SMS_SIGN_USED_BEFORE` | Sign name already exists | Use different name or query existing |
| `isv.SMS_TEMPLATE_USED_BEFORE` | Template already exists | Use different name or query existing |
| `isv.BUSINESS_LIMIT_CONTROL` | Rate limit exceeded | Back off exponentially; respect Retry-After |
| `isv.AMOUNT_NOT_ENOUGH` | Balance insufficient | HALT; user must recharge |
| `isv.DAY_AMOUNT_LIMIT` | Daily quota exceeded | HALT; daily send limit reached |
| `isv.TEMPLATE_MISSING` | Template code not found | Verify template code exists |
| `isv.TEMPLATE_CONTENT_LIMIT` | Template content too long | Reduce content to ≤500 chars |
| `isv.SMS_SIGN_FILE_INVALID` | Sign image invalid | Upload valid image file |
| `isv.PACKAGE_EXPIRED` | SMS package has expired | Purchase new package or renew |
| `isv.PACKAGE_USAGE_EXHAUSTED` | SMS package usage exhausted | Purchase new package |
| `isv.PACKAGE_NOT_ACTIVATED` | SMS package not activated | Activate package via console |
| `Forbidden.RAM` / 403 | Insufficient permissions | User adds RAM policy for dysmsapi |
| `InvalidAccessKey` / 403 | Access key invalid | Verify credentials |
| `Throttling` / 429 | Rate limit | Back off exponentially |
| `InternalError` / 5xx | Server error | Retry with backoff; then HALT with RequestId |

## Diagnostic Order

1. **Verify credentials**: `aliyun dysmsapi QuerySendStatistics --StartDate "$(date +%Y-%m-%d)" --EndDate "$(date +%Y-%m-%d)"`
2. **Check signature status**: `aliyun dysmsapi QuerySmsSign --SignName "你的签名"`
3. **Check template status**: `aliyun dysmsapi QuerySmsTemplate --TemplateCode "SMS_xxx"`
4. **Verify phone number format**: 11-digit mobile number
5. **Check API quota**: Verify daily/monthly limits

## Common Issues

### SMS Not Delivered
- **Check signature**: Must be approved (SignStatus=1)
- **Check template**: Must be approved (TemplateStatus=1)
- **Check phone number**: Valid 11-digit format
- **Check template params**: Must match `${variable}` placeholders
- **Check delivery status**: QuerySendDetails for ErrCode/ErrMsg

### Signature/Template Rejected
- **Review rejection reason**: QuerySmsSign/QuerySmsTemplate returns Reason
- **Fix content**: Ensure no forbidden words or format issues
- **Resubmit**: ModifySmsSign/ModifySmsTemplate after fixes

### Rate Limiting
- **Per-signature limit**: 1 SMS per 100ms
- **Per-account limit**: Check QuerySendStatistics
- **Backoff strategy**: Exponential backoff on `isv.BUSINESS_LIMIT_CONTROL`

### Batch Send Failures
- **Array length mismatch**: Phone numbers, signatures, and params must have same count
- **JSON format**: Ensure valid JSON arrays
- **Template compatibility**: All numbers must use same template

### Verification Code Issues
- **Template type**: Must be verification type (TemplateType=0)
- **Code format**: 4-6 digits recommended
- **Validity**: 5-10 minutes typical
- **Rate limit**: Max 1 SMS per phone per minute

## SMS Package-Related Issues

### Common Package Issues

1. **Package Balance Insufficient**: `isv.AMOUNT_NOT_ENOUGH` error when sending SMS
2. **Package Expired**: SMS package has expired and is no longer valid
3. **Package Not Activated**: Purchased package not activated for use
4. **Package Usage Exhausted**: All SMS in the package have been used

### Troubleshooting Steps
1. **Check Package Details**: Use the Alibaba Cloud console or `aliyun bssopenapi QueryResourcePackageList` to view SMS package details
2. **Verify Expiry Date**: Confirm the package has not expired
3. **Check Usage Statistics**: Use `aliyun dysmsapi QuerySendStatistics` to compare usage against package limits
4. **Recharge or Purchase New Package**: If usage is exhausted, purchase a new SMS package

### Recovery Strategies
1. For `isv.AMOUNT_NOT_ENOUGH`: Purchase additional SMS packages or recharge your account
2. For expired packages: Renew or purchase a new package
3. For unactivated packages: Activate the package via the Alibaba Cloud console

## Recovery Strategies

### Signature/Template Not Ready
1. Query current status
2. If rejected, review Reason field
3. Fix issues and use Modify operation
4. Resubmit for approval
5. Poll status until approved

### Send Failures
1. Check error code from API response
2. Fix parameter issues (phone, template, signature)
3. Retry with correct parameters
4. For rate limits, implement backoff

### Quota Exceeded
1. Query current usage via QuerySendStatistics
2. Check daily/monthly limits
3. Wait for quota reset (daily) or contact support (monthly)

### SMS Package Issues
1. Follow the SMS Package-Related Issues troubleshooting steps above

## Error Code Reference

| Error Code | Category | Action |
|------------|----------|--------|
| InvalidParameter | Input | Fix parameters |
| isv.SMS_SIGNATURE_ILLEGAL | Signature | Fix signature |
| isv.SMS_TEMPLATE_ILLEGAL | Template | Fix template |
| isv.BUSINESS_LIMIT_CONTROL | Rate | Backoff |
| isv.AMOUNT_NOT_ENOUGH | Billing | Recharge |
| isv.PACKAGE_EXPIRED | Billing | Purchase new package/renew |
| isv.PACKAGE_USAGE_EXHAUSTED | Billing | Purchase new package |
| isv.PACKAGE_NOT_ACTIVATED | Billing | Activate package |
| isv.DAY_AMOUNT_LIMIT | Quota | Wait/HALT |
| isv.TEMPLATE_MISSING | Template | Verify code |
| isv.SMS_SIGN_USED_BEFORE | Signature | Use new name |
| isv.SMS_TEMPLATE_USED_BEFORE | Template | Use new name |
| Forbidden.RAM | Permission | Add RAM policy |
| InvalidAccessKey | Auth | Fix credentials |
| Throttling | Rate | Backoff |
| InternalError | Server | Retry/HALT |
