# Troubleshooting Alibaba Cloud GCL Runner

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `RUBRIC_ERROR` | 4 | 评分标准解析错误 | 检查 rubric.md 格式 |
| `SAFETY_FAIL` | 2 | 安全检查失败 | 检查命令安全性 |
| `MAX_ITER` | 1 | 达到最大迭代次数 | 增加 max_iter 或检查 rubric 阈值 |
| `USAGE_ERROR` | 3 | 参数错误 | 检查命令行参数 |
| `InternalError` / 500 | Server-side error | Retry with backoff; then HALT |
| `Throttling` / 429 | Rate limit exceeded | Back off exponentially |
| `Forbidden.RAM` / 403 | Insufficient RAM permissions | Add RAM policy |

## Diagnostic Order

1. **Verify resource exists**: Describe by ID
2. **Check status**: Ensure resource is in expected state
3. **Check region**: Verify correct RegionId
4. **Verify credentials**: Test with simple `Describe` operation
5. **Check quotas**: Verify service quotas not exceeded

## Common Issues

### Authentication Failures
- Verify `ALIBABA_CLOUD_ACCESS_KEY_ID` is set
- Verify `ALIBABA_CLOUD_ACCESS_KEY_SECRET` is correct
- Check RAM user has required permissions

### Resource Not Found
- Verify resource ID format
- Check resource exists in correct region
- Resource may have been deleted

### Quota Exceeded
- Check current usage vs limits
- Request quota increase if needed
- Clean up unused resources

## Getting Help

- **OpenAPI Explorer**: https://api.aliyun.com/
- **Documentation**: https://www.alibabacloud.com/help/en/gcl
- **Support**: Submit ticket via Alibaba Cloud Console
