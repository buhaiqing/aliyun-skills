# EIP Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for EIP (Elastic IP). Each pattern follows the standardized schema.

## EIP-001 — EIP 黑洞（DDoS 攻击）

| 属性 | 内容 |
|------|------|
| 触发指标 | DropPacketBlackHole > 0 AND InternetIn 突增 5x+ |
| 触发阈值 | 黑洞阈值被触发 |
| 典型特征 | 入流量突增、出流量为 0（黑洞）所有流量被丢弃 |
| 关联指标 | BPS 达到上限、PPS 飙升 |
| 根因 | 1. DDoS 攻击 2. 流量反射/放大攻击 3. 端口暴露 |
| 诊断步骤 | 1. 查 DDoS 控制台 2. FlowLog 分析源 IP 分布 3. 协议分析 |
| 修复方案 | 1. 启用 DDoS 高防 2. 清洗流量 3. 临时切换 EIP |
| 预防措施 | DDoS 高防预配、端口最小暴露、IP 地址轮换 |

## EIP-002 — 带宽持续饱和

| 属性 | 内容 |
|------|------|
| 触发指标 | Bandwidth Utilization > 90% 持续 10 min |
| 触发阈值 | 带宽 > 90% 上限 |
| 典型特征 | 请求超时、TCP 重传增加、用户体验下降 |
| 关联指标 | ActiveConnection 不降但流量饱和 |
| 根因 | 1. 大文件下载 2. 爬虫/数据爬取 3. 配置未限制速率 |
| 诊断步骤 | 1. 查流量分布 2. 分析 Top 源 IP 3. 确认目标应用 |
| 修复方案 | 1. 临时升级带宽 2. 限流 3. CDN 分流 |
| 预防措施 | 带宽 80% 预警、CDN 预部署、限流策略 |

## EIP-003 — 连接数耗尽

| 属性 | 内容 |
|------|------|
| 触发指标 | ActiveConnection 接近单 EIP 上限 (~30K) |
| 触发阈值 | 连接数 > 25K 持续 5 min |
| 典型特征 | 新连接被拒绝，客户端超时 |
| 关联指标 | DropConnection 非零、NewConnection 下降 |
| 根因 | 1. 连接泄漏（未释放）2. 大量长连接 3. 客户端重试风暴 |
| 诊断步骤 | 1. `netstat` 连接状态 2. 客户端连接分析 3. 超时配置 |
| 修复方案 | 1. 清理空闲连接 2. 优化超时 3. 添加 EIP 扩容 |
| 预防措施 | 连接数监控、idle timeout 配置、连接池优化 |

## EIP-004 — 绑定/解绑失败

| 属性 | 内容 |
|------|------|
| 触发指标 | AssociateEipAddress / UnassociateEipAddress 失败 |
| 触发阈值 | 操作失败持续 > 2 min |
| 典型特征 | EIP 状态为 Associating/Unassociating 卡住 |
| 关联指标 | EIP 和实例状态不一致 |
| 根因 | 1. 实例状态异常（如停机）2. 不同 Region 3. 实例未分配弹性网卡 |
| 诊断步骤 | 1. DescribeEipAddresses 查状态 2. 查目标实例状态 3. Region 匹配 |
| 修复方案 | 1. 确保同 Region 2. 实例需 Running 状态 |
| 预防措施 | 绑定前状态校验、自动化脚本中 Region 一致性检查 |

## EIP-005 — 计费模式切换异常

| 属性 | 内容 |
|------|------|
| 触发指标 | ModifyEipAddressAttribute 失败 |
| 触发阈值 | 计费模式切换操作失败 |
| 典型特征 | 计费模式未变更或变更中状态 |
| 关联指标 | 账户状态异常时切换失败 |
| 根因 | 1. 账户余额不足 2. 实例正在变更中 3. 不支持当前配置 |
| 诊断步骤 | 1. 查账户余额 2. 确认当前计费状态 3. 查操作限制 |
| 修复方案 | 1. 充值账户 2. 等待变更完成 |
| 预防措施 | 变更前检查余额和状态、自动化脚本幂等性 |

## Cross-Product — EIP 黑洞 → SLB 5xx 级联故障

**场景：** EIP 被 DDoS 攻击进入黑洞 → SLB 公网访问不可达 → 5xx

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | EIP 黑洞触发，所有流量丢弃 | `alicloud-eip-ops` |
| T1 | +1 min | SLB 公网入口不可达，流量突降至 0 | `alicloud-slb-ops` |
| T2 | +5 min | 用户报告服务完全不可用 | `alicloud-slb-ops` + SLB 后端正常 |

**诊断顺序：** SLB 5xx 后看 EIP 黑洞告警 → 启用 DDoS 高防切流