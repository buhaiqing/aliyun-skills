# 安全门规范 (Safety Gate)

## 核心原则

本 Skill 的所有执行路径必须严格遵守 **只读 (Read-Only)** 策略。

## 允许的操作

| API 前缀 | 说明 |
|---------|------|
| `Describe*` | 查询资源详情列表 |
| `List*` | 查询资源列表 |
| `Get*` | 查询单个资源详情 |

## 禁止的操作

| API 前缀 | 风险说明 |
|---------|---------|
| `Create*` | 创建/新建资源 |
| `Delete*` | 删除/释放资源 |
| `Modify*` | 修改配置/状态 |
| `Update*` | 更新资源信息 |
| `Associate*` | 关联绑定 (如 EIP 绑定) |
| `Unassociate*` | 解绑/分离资源 |
| `Authorize*` | 授权 (如安全组规则) |
| `Revoke*` | 撤销授权 |
| `Stop*` | 停止/关机实例 |
| `Start*` | 启动/开机实例 |
| `Reboot*` | 重启实例 |
| `Run*` / `Invoke*` | 执行命令/调用动作 |
| `Attach*` / `Detach*` | 挂载/卸载磁盘 |
| `Release*` | 释放资源 |

## 执行前验

所有 CLI 命令在执行前必须经过正则匹配验证：
```python
ALLOWED_PATTERN = r"^(Describe|List|Get)"
```
任何不匹配上述模式的命令将导致程序立即终止 (HALT)。
