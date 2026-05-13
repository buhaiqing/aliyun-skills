# Troubleshooting ACK

## Common API Error Codes

| Code / HTTP | Meaning | Agent Action |
|-------------|---------|--------------|
| `ErrorClusterNotFound` / 404 | Cluster does not exist | Verify `cluster_id`; may already be deleted |
| `ErrorClusterState` / 400 | Cluster not in valid state for operation | Wait for cluster to reach stable state (`running`) |
| `ErrorCheckAcl` / 403 | RAM permission denied | Delegate to RAM skill or user adds `cs:*` policy |
| `InvalidParameter` / 400 | Request validation failed | Align body with OpenAPI spec; check `vpc_id`, `vswitch_ids` |
| `QuotaExceeded.Cluster` / 400 | Cluster quota exceeded | HALT; user raises quota via console or ticket |
| `QuotaExceeded.Node` / 400 | Node quota exceeded | HALT; user raises quota |
| `InsufficientBalance` / 400 | Account balance insufficient | HALT |
| `DependencyResourceExist` / 400 | Resources still bound to cluster | Ask user to release SLB, PVCs, or other dependencies |
| `InternalError` / 500 | Server-side error | Retry with backoff; then HALT with `RequestId` |

## Diagnostic Order

1. **Describe cluster** by ID: `aliyun cs GET /clusters/{cluster_id}`
2. **Check cluster state:** `$.state` should be `running` for most operations
3. **List nodes:** `aliyun cs GET /clusters/{cluster_id}/nodes` to check node health
4. **List node pools:** `aliyun cs GET /clusters/{cluster_id}/nodepools` to check pool state
5. **Verify regional endpoint:** Ensure `RegionId` matches cluster region
6. **Check CLI metadata:** `aliyun help cs` for available operations

## Cluster State Reference

| State | Meaning | Actionable? |
|-------|---------|-------------|
| `initial` | Creating | Wait |
| `running` | Healthy | Yes |
| `updating` | Upgrading or scaling | Wait |
| `failed` | Creation or operation failed | Check logs; may need to delete and recreate |
| `deleting` | Deleting | Wait |
| `deleted` | Deleted | N/A |

## Node Pool State Reference

| State | Meaning | Actionable? |
|-------|---------|-------------|
| `active` | Healthy | Yes |
| `scaling` | Scaling in progress | Wait |
| `updating` | Updating | Wait |
| `failed` | Failed | Check error message; may need to recreate |
| `deleting` | Deleting | Wait |
