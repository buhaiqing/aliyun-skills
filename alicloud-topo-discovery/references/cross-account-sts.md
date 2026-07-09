# Cross-Account STS AssumeRole 设置指南

本 skill 的 `scan-topo` 和 `export-hcl` 命令支持 `--assume-role` 参数,通过 STS AssumeRole 跨账号读取资源。

## 前提条件

1. 目标账号有一个角色,信任策略允许当前账号扮演
2. 角色至少附加 `AliyunReadOnlyAccess` 策略
3. 当前账号的 AK 已配置(通过环境变量)

## 角色信任策略模板

```json
{
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Principal": {
        "RAM": ["acs:ram::<源账号ID>:root"]
      },
      "Condition": {}
    }
  ]
}
```

## 使用方式

```bash
# 单账号模式(默认)
./topo-scan.sh

# 跨账号模式
./topo-scan.sh --assume-role arn:acs:ram::1234567890:role/TopologyReader

# 指定 session 名称和时长
export-hcl.py --scope all \
    --assume-role arn:acs:ram::1234567890:role/TopologyReader \
    --session-name "my-scan" \
    --duration 7200 \
    --output-dir ./hcl-export/
```

## 安全约束

- 临时凭证**永不**写入 manifest.json、日志或输出文件
- 凭证仅在脚本内存中存活,执行完毕后丢弃
- 失败时 HALT,绝不带主账号凭证"兜底"
- 角色必须严格满足 `AliyunReadOnlyAccess` 权限

## 故障排查

| 错误 | 原因 | 修复 |
|------|------|------|
| `ASSume_ROLE_FAILED` | API 调用失败 | 检查角色 ARN、权限和网络 |
| `Empty credentials` | STS 返回空令牌 | 检查角色信任策略 |
| `Invalid role ARN` | ARN 格式错误 | 使用 `arn:acs:ram::<account_id>:role/<name>` 格式 |
| `Missing credentials` | 未设置 AK | 设置 `ALIBABA_CLOUD_ACCESS_KEY_ID` 和 `SECRET` |