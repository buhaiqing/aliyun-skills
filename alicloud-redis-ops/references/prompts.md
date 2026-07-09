# Prompts Guide — Alibaba Cloud Redis / Tair (KVStore)

> **Purpose:** This document provides ready-to-use prompt templates for common operational scenarios. Copy-paste these prompts (or adapt them) when interacting with an AI agent equipped with the `alicloud-redis-ops` skill.

---

## How to Use This Guide

1. **Identify your scenario** from the categories below.
2. **Copy the prompt template** and fill in the `{{placeholders}}`.
3. **Send to the AI agent** — it will invoke the appropriate operations from `alicloud-redis-ops`.

---

## 1. Instance Lifecycle Management

### 1.1 Create a New Redis Instance

```
请帮我在 {{region}} 区域创建一个 Redis {{engine_version}} 实例，
规格为 {{instance_class}}，实例名称为 "{{instance_name}}"。
要求：
- 网络类型：VPC
- VPC ID：{{vpc_id}}
- VSwitch ID：{{vswitch_id}}
- 付费类型：{{charge_type|PostPaid}}
- 密码：{{password}}

创建完成后，请返回实例 ID、连接地址和端口。
```

**Example:**
```
请帮我在 cn-hangzhou 区域创建一个 Redis 6.0 实例，
规格为 redis.shard.small.2ca，实例名称为 "my-prod-cache"。
要求：
- 网络类型：VPC
- VPC ID：vpc-bp1xxxxxxxx
- VSwitch ID：vsw-bp1xxxxxxxx
- 付费类型：PostPaid
- 密码：MyP@ssw0rd123

创建完成后，请返回实例 ID、连接地址和端口。
```

### 1.2 List All Instances in a Region

```
请列出我在 {{region}} 区域的所有 Redis/Tair 实例，
包括：实例 ID、实例名称、状态、规格、引擎版本、创建时间。
```

### 1.3 Check Instance Details

```
请查询实例 {{instance_id}} 的详细信息，包括：
- 实例状态
- 连接地址和端口
- 容量、带宽、最大连接数
- 安全 IP 白名单
- 维护时间窗口
- SSL 状态
```

### 1.4 Restart an Instance

```
请帮我重启实例 {{instance_id}}。
注意：
- 请确认实例当前状态为 Normal
- 重启会造成短暂连接中断，请提前确认
- 重启后请验证实例状态恢复为 Normal
```

### 1.5 Delete an Instance

```
请帮我删除实例 {{instance_id}}。
注意：
- 此操作不可逆，所有数据将被删除
- 请确认实例 ID 正确
- 删除后请验证实例已不存在
```

### 1.6 Scale Instance (Vertical Scaling)

```
请将实例 {{instance_id}} 的规格从当前规格升级为 {{target_instance_class}}。
注意：
- 请确认当前实例状态为 Normal
- 变配会造成短暂连接中断
- 变配完成后请验证实例状态和新规格
```

---

## 2. Account Management

### 2.1 Create a Database Account

```
请为实例 {{instance_id}} 创建一个数据库账号：
- 账号名：{{account_name}}
- 密码：{{password}}
- 账号类型：{{account_type|Normal}}

创建完成后请验证账号状态为 Available。
```

### 2.2 List All Accounts

```
请列出实例 {{instance_id}} 的所有数据库账号，
包括：账号名、账号类型、账号状态。
```

### 2.3 Reset Account Password

```
请重置实例 {{instance_id}} 的账号 {{account_name}} 的密码为：{{new_password}}。
注意：
- 密码重置会影响所有使用该账号的连接
- 重置后请验证账号状态恢复为 Available
```

### 2.4 Delete an Account

```
请删除实例 {{instance_id}} 的账号 {{account_name}}。
注意：此操作不可逆，请确认账号名正确。
删除后请验证该账号已不存在。
```

---

## 3. Backup and Recovery

### 3.1 Create a Manual Backup

```
请为实例 {{instance_id}} 创建一个手动备份。
备份完成后请返回：备份 ID、备份状态、备份大小、开始时间和结束时间。
```

### 3.2 List Backups

```
请列出实例 {{instance_id}} 的所有备份，
包括：备份 ID、备份类型（自动/手动）、备份状态、备份大小、备份时间。
```

### 3.3 Restore from Backup

```
请使用备份 {{backup_id}} 恢复实例 {{instance_id}}。
注意：
- 恢复操作会覆盖当前实例数据
- 请确认备份 ID 正确
- 恢复完成后请验证实例状态为 Normal
```

---

## 4. Security (Whitelist)

### 4.1 View Current Whitelist

```
请查询实例 {{instance_id}} 的当前安全 IP 白名单配置，
包括：白名单分组名称、IP 列表。
```

### 4.2 Modify Whitelist

```
请将实例 {{instance_id}} 的安全 IP 白名单修改为：{{security_ips}}。
注意：
- 修改白名单会影响数据库访问
- 请确保包含所有必要的客户端 IP
- 修改后请验证白名单已更新
```

### 4.3 Add IP to Whitelist

```
请将 IP {{new_ip}} 添加到实例 {{instance_id}} 的安全 IP 白名单中，
保留现有的白名单配置。
```

---

## 5. Parameter Management

### 5.1 List All Parameters

```
请列出实例 {{instance_id}} 的所有可配置参数，
包括：参数名、当前值、默认值、是否可修改、参数描述。
```

### 5.2 Modify a Parameter

```
请将实例 {{instance_id}} 的参数 {{parameter_name}} 修改为 {{parameter_value}}。
注意：
- 请确认参数可修改
- 部分参数修改需要重启实例才能生效
- 修改后请验证参数值已更新
```

### 5.3 Optimize for High Concurrency

```
请为实例 {{instance_id}} 优化以下参数以支持高并发场景：
- maxmemory-policy：建议设置为 allkeys-lru 或 volatile-lru
- timeout：根据业务需求调整
- tcp-keepalive：建议启用

请列出当前值和建议值，并帮我应用优化后的配置。
```

---

## 6. Monitoring and Diagnostics

### 6.1 Quick Health Check

```
请对实例 {{instance_id}} 进行健康检查，包括：
1. 实例状态是否正常
2. 最近 1 小时的性能指标（CPU、内存、连接数、QPS、延迟）
3. 最近 1 小时的慢查询日志
4. 白名单配置

请生成一份健康检查报告。
```

### 6.2 Performance Analysis

```
请分析实例 {{instance_id}} 在最近 {{time_range|1小时}} 的性能数据：
1. CPU 使用率趋势
2. 内存使用率趋势
3. 连接数趋势
4. QPS 趋势
5. 平均延迟和最大延迟
6. 缓存命中率

如果发现异常，请指出可能的原因和建议的优化措施。
```

### 6.3 Slow Query Analysis

```
请分析实例 {{instance_id}} 在最近 {{time_range|1小时}} 的慢查询日志：
1. 慢查询数量
2. 最慢的 10 条命令
3. 慢查询模式分析（是否有重复出现的慢命令）
4. 优化建议
```

### 6.4 Connection Analysis

```
请分析实例 {{instance_id}} 的连接使用情况：
1. 当前连接数
2. 连接使用率
3. 最大连接数限制
4. 如果连接数接近上限，请给出优化建议
```

---

## 7. Troubleshooting

### 7.1 Cannot Connect to Redis

```
我的应用无法连接到 Redis 实例 {{instance_id}}，错误信息是：{{error_message}}。
请帮我排查：
1. 实例状态是否正常
2. 安全 IP 白名单是否包含应用服务器 IP
3. 连接地址和端口是否正确
4. 密码是否正确
5. SSL 配置是否匹配

请给出诊断结果和解决方案。
```

### 7.2 High CPU Usage

```
实例 {{instance_id}} 的 CPU 使用率突然升高，请帮我：
1. 查看最近 1 小时的 CPU 使用率趋势
2. 查看 QPS 趋势
3. 分析慢查询日志
4. 找出可能导致 CPU 高的原因
5. 给出优化建议
```

### 7.3 High Memory Usage / OOM Risk

```
实例 {{instance_id}} 的内存使用率超过 80%，请帮我：
1. 查看内存使用趋势
2. 查看 Key 数量、过期 Key 数量、驱逐 Key 数量
3. 检查 maxmemory-policy 配置
4. 评估 OOM 风险
5. 给出优化建议（数据清理、扩容、参数优化等）
```

### 7.4 High Latency

```
实例 {{instance_id}} 的响应延迟明显增高，请帮我：
1. 查看平均延迟和最大延迟趋势
2. 分析慢查询日志
3. 检查是否存在大 Key 或热 Key
4. 检查网络延迟
5. 给出优化建议
```

### 7.5 Replication Lag

```
实例 {{instance_id}} 的主从复制延迟很大，请帮我：
1. 查看复制延迟趋势
2. 检查主实例负载
3. 检查网络带宽使用情况
4. 分析可能的原因
5. 给出优化建议
```

---

## 8. Maintenance Operations

### 8.1 Modify Maintenance Window

```
请将实例 {{instance_id}} 的维护时间窗口修改为：
- 开始时间：{{maintain_start_time}}
- 结束时间：{{maintain_end_time}}

注意：修改维护窗口可能影响定时维护任务的执行时间。
```

### 8.2 Enable/Disable SSL

```
请为实例 {{instance_id}} {{action|启用}} SSL 加密连接。
注意：
- 启用/禁用 SSL 会造成短暂连接中断
- 请确认应用已配置支持 SSL（如启用）
- 操作完成后请验证 SSL 状态
```

### 8.3 Modify Intranet Bandwidth

```
请将实例 {{instance_id}} 的内网带宽修改为 {{bandwidth}} MB/s。
注意：
- 请确认当前带宽限制
- 修改后请验证带宽已更新
```

### 8.4 Migrate to Another Zone

```
请将实例 {{instance_id}} 迁移到可用区 {{zone_id}}。
注意：
- 迁移会造成短暂连接中断
- 请确认目标可用区支持当前实例规格
- 迁移完成后请验证实例状态为 Normal
```

### 8.5 Upgrade Minor Version

```
请将实例 {{instance_id}} 的小版本升级到最新版本。
注意：
- 升级会造成短暂连接中断
- 请确认当前版本和可升级版本
- 升级完成后请验证实例状态为 Normal
```

### 8.6 Flush Instance (Clear All Data)

```
请清空实例 {{instance_id}} 的所有数据。
注意：
- 此操作不可逆，所有数据将被删除
- 强烈建议先创建备份
- 请确认实例 ID 正确
- 清空后请验证实例状态为 Normal
```

---

## 9. Tair-Specific Operations

### 9.1 Check Tair Data Type Support

```
请检查实例 {{instance_id}} 是否支持 Tair 扩展数据类型，
并返回支持的 Tair 数据类型列表。
```

### 9.2 Persistent Memory Performance Check

```
我的 Tair 持久内存实例 {{instance_id}} 性能下降，请帮我：
1. 检查持久内存使用率
2. 检查内存层级命中率
3. 分析可能的原因
4. 给出优化建议
```

---

## 10. Batch Operations

### 10.1 Batch Create Instances

```
请帮我批量创建 {{count}} 个 Redis 实例，配置如下：
- 区域：{{region}}
- 引擎版本：{{engine_version}}
- 规格：{{instance_class}}
- 网络类型：VPC
- VPC ID：{{vpc_id}}
- VSwitch ID：{{vswitch_id}}

实例名称前缀：{{name_prefix}}
请返回所有创建成功的实例 ID 列表。
```

### 10.2 Batch Restart Instances

```
请帮我批量重启以下实例：{{instance_id_list}}。
注意：
- 请逐个确认每个实例状态为 Normal
- 重启会造成短暂连接中断
- 每个实例重启后请验证状态恢复为 Normal
```

### 10.3 Batch Modify Whitelist

```
请将以下实例 {{instance_id_list}} 的安全 IP 白名单
都修改为：{{security_ips}}。
注意：
- 修改后请逐个验证白名单已更新
```

---

## 11. Advanced Scenarios

### 11.1 Capacity Planning Report

```
请为实例 {{instance_id}} 生成一份容量规划报告，包括：
1. 最近 7 天的资源使用趋势（CPU、内存、连接数、QPS）
2. 峰值使用率和平均使用率
3. 容量增长趋势预测
4. 是否需要扩容的建议
5. 推荐的实例规格（如需要扩容）
```

### 11.2 Security Audit

```
请对实例 {{instance_id}} 进行安全审计，包括：
1. 安全 IP 白名单配置审查
2. 数据库账号审查（账号数量、权限、密码策略）
3. SSL 配置状态
4. 安全建议和整改措施
```

### 11.3 Disaster Recovery Check

```
请检查实例 {{instance_id}} 的灾备状态，包括：
1. 最近备份时间和备份状态
2. 备份保留策略
3. 跨可用区部署状态
4. 灾备建议和整改措施
```

### 11.4 Cost Optimization

```
请分析实例 {{instance_id}} 的资源使用情况，给出成本优化建议：
1. 当前规格与实际负载的匹配度
2. 是否存在资源浪费（低 CPU/内存使用率）
3. 是否可以通过降配或变更架构来降低成本
4. 具体的优化方案和预期节省
```

---

## Prompt Design Tips

### Best Practices

1. **Be Specific:** Always provide `instance_id` and `region` when applicable.
2. **State Constraints:** Mention if the operation should avoid downtime or data loss.
3. **Request Verification:** Ask the agent to verify the result after operations.
4. **Provide Context:** Include error messages or symptoms for troubleshooting prompts.
5. **Use Placeholders:** Use `{{placeholder}}` for values that need to be filled in.

### Safety Reminders

- **Destructive operations** (delete, flush, restore) should always include explicit confirmation.
- **Scaling operations** should mention potential brief connection interruption.
- **Password-related** prompts should remind about security best practices.

### Example: Complete Troubleshooting Workflow

```
我的应用报告无法连接到 Redis 实例，错误是 "Connection timed out"。
实例 ID 是 r-bp1xxxxxxxxxxxxx，区域是 cn-hangzhou。
应用服务器 IP 是 192.168.1.100。

请帮我：
1. 检查实例状态是否正常
2. 检查安全 IP 白名单是否包含 192.168.1.100
3. 检查连接地址和端口是否正确
4. 如果白名单有问题，请帮我添加该 IP
5. 验证连接问题是否解决
```

---

*Last updated: 2026-05-14*
