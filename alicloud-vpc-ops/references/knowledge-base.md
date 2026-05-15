# VPC Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for VPC networking resources (VPC, vSwitch, NAT, EIP). Each pattern follows the standardized schema.

## VPC-001 — 路由冲突

| 属性 | 内容 |
|------|------|
| 触发指标 | 同 CIDR 路由条目冲突 |
| 触发阈值 | 路由表中存在重叠 CIDR 的多条路由 |
| 典型特征 | 部分子网无法访问，网络间歇性中断 |
| 关联指标 | FlowLog 中部分流量被路由到错误出口 |
| 根因 | 1. 手动添加冲突路由 2. VPN/CCN 路由注入 3. 路由优先级配置错误 |
| 诊断步骤 | 1. DescribeRouteTables 查路由 2. 对比历史路由 3. 查 VPN/CCN 路由表 |
| 修复方案 | 1. 删除冲突路由 2. 修正路由优先级 |
| 预防措施 | 路由变更审批流程、自动冲突检测、CEN 路由策略审查 |

## VPC-002 — vSwitch CIDR 耗尽

| 属性 | 内容 |
|------|------|
| 触发指标 | vSwitch 可用 IP < 10% |
| 触发阈值 | 可用 IP 数 < 10 个 |
| 典型特征 | 新 ECS 实例无法创建在指定 vSwitch，Pod 无法调度到该可用区 |
| 关联指标 | 集群调度事件 FailedScheduling 增加 |
| 根因 | 1. 子网掩码过小 (/24) 2. IP 泄漏（实例创建但未释放） |
| 诊断步骤 | 1. DescribeVSwitches 查已分配 IP 2. 确认实例是否已释放 |
| 修复方案 | 1. 创建新 vSwitch 2. 升级 VPC CIDR（如允许） |
| 预防措施 | 初始规划 vSwitch 至少 /20，监控可用 IP 数 |

## VPC-003 — VPN 连接断开

| 属性 | 内容 |
|------|------|
| 触发指标 | Ipsec 连接状态 = DOWN |
| 触发阈值 | 连接断开 > 5 min |
| 典型特征 | 专线/混合云中断，跨机房通信中断 |
| 关联指标 | VPC 出入流量突降 |
| 根因 | 1. IPsec 配置变更 2. 对端设备异常 3. 网络中断 |
| 诊断步骤 | 1. 查 VPN 网关状态 2. 查对端 IPsec 配置 3. ping 测试 |
| 修复方案 | 1. 恢复 IPsec 配置 2. 重启隧道 3. 联系对端网络团队 |
| 预防措施 | VPN 状态持续监控、备用隧道、对端设备定期巡检 |

## VPC-004 — 网络 ACL 误配

| 属性 | 内容 |
|------|------|
| 触发指标 | vSwitch 流量突降 + FlowLog 中 REJECT 增加 |
| 触发阈值 | 入/出方向被拒绝的流量 > 100/min |
| 典型特征 | 特定端口/网段无法访问，服务部分中断 |
| 关联指标 | 应用错误日志中 Connect timeout 增加 |
| 根因 | 1. ACL 规则配置错误 2. ACL 关联到错误 vSwitch 3. 顺序优先级问题 |
| 诊断步骤 | 1. DescribeNetworkAclEntries 2. 确认规则顺序 3. 对比变更前 |
| 修复方案 | 修正 ACL 规则顺序/配置 |
| 预防措施 | ACL 变更审批、变更前后流量基线对比 |

## VPC-005 — 安全组规则异常

| 属性 | 内容 |
|------|------|
| 触发指标 | 端口不可达 + 安全组 DENY 日志 |
| 触发阈值 | 关键端口（80/443/22）不可达 > 2 min |
| 典型特征 | 应用无法从外部/内部访问指定端口 |
| 关联指标 | SLB 健康检查失败 |
| 根因 | 1. 误删除安全组规则 2. 关联关系变更 3. 权限被其他用户修改 |
| 诊断步骤 | 1. DescribeSecurityGroupAttribute 2. ActionTrail 查变更历史 |
| 修复方案 | 恢复安全组规则 |
| 预防措施 | 安全组变更通知、禁止非自动化变更 |

## VPC-006 — VPC 对等连接/CCN 路由泄漏

| 属性 | 内容 |
|------|------|
| 触发指标 | DescribeVpcRouteTables 中出现未知来源的路由 |
| 触发阈值 | 路由数量突增 > 50% |
| 典型特征 | 跨 VPC 通信异常，特定网段路由混乱 |
| 关联指标 | 跨 VPC 流量异常 |
| 根因 | 1. 对等连接配置错误 2. CCN 路由传播 3. 网段重叠 |
| 诊断步骤 | 1. 查路由来源 2. 检查 VPC 间连接配置 3. 确认网段规划 |
| 修复方案 | 1. 修正路由传播 2. 隔离冲突网段 |
| 预防措施 | VPC 网段统一规划、路由传播审批 |

## Cross-Product — VPC → ECS → RDS 网络级联故障

**场景：** VPC 路由变更 → ECS 无法连接 RDS → 服务不可用

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | VPC 默认路由被删除或修改 | `alicloud-vpc-ops` |
| T1 | +10s | ECS 实例无法访问 NAT/内网 | `alicloud-ecs-ops` |
| T2 | +30s | ECS 连接 RDS 超时，连接池耗尽 | `alicloud-rds-ops` |
| T3 | +2 min | SLB 后端不可用，5xx 爆发 | `alicloud-slb-ops` |

**诊断顺序：** SLB 5xx → ECS 连接 RDS 超时 → 查 VPC 路由表 → 恢复路由