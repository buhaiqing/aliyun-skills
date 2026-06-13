# Troubleshooting Alibaba Cloud ResourceManager

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `EntityNotExists.Folder` | 404 | 文件夹不存在 | 验证 FolderId |
| `EntityNotExists.ResourceGroup` | 404 | 资源组不存在 | 验证 ResourceGroupId |
| `NoPermission` | 403 | 无权限 | 检查 RAM 权限 |
| `InvalidParameter` | 400 | 参数无效 | 检查请求参数 |
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
- **Documentation**: https://www.alibabacloud.com/help/en/resourcemanager
- **Support**: Submit ticket via Alibaba Cloud Console
