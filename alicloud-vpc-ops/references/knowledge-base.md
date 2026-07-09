# VPC Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for VPC networking resources. Each pattern: trigger → diagnose → fix.

| # | Pattern | Trigger | Diagnosis | Fix |
|---|---------|---------|-----------|-----|
| 001 | 路由冲突 | 同CIDR路由冲突 → 部分子网无法访问 | DescribeRouteTables → 对比历史路由 | 删除冲突路由，修正优先级 |
| 002 | vSwitch CIDR 耗尽 | 可用IP < 10% → 新ECS/Pod创建失败 | DescribeVSwitches 查已分配IP | 创建新vSwitch，规划至少/20 |
| 003 | VPN 连接断开 | IPsec状态=DOWN > 5min → 混合云中断 | 查VPN网关状态 → 查对端配置 → ping | 恢复配置，重启隧道 |
| 004 | 网络 ACL 误配 | 流量突降+REJECT > 100/min → 服务部分中断 | DescribeNetworkAclEntries → 确认规则顺序 | 修正ACL规则/顺序 |
| 005 | 安全组规则异常 | 端口不可达+DENY日志 > 2min | DescribeSecurityGroupAttribute + ActionTrail | 恢复安全组规则 |
| 006 | VPC 对等连接/CCN 路由泄漏 | 路由数量突增 > 50% | 查路由来源 → 查VPC间连接配置 | 修正路由传播，隔离冲突网段 |

## Cross-Product — VPC → ECS → RDS 级联故障

VPC路由变更 → ECS无法连接RDS → 服务不可用

| 阶段 | 现象 | Skill |
|------|------|-------|
| T0 | VPC默认路由被删除/修改 | `alicloud-vpc-ops` |
| T1+10s | ECS无法访问NAT/内网 | `alicloud-ecs-ops` |
| T2+30s | ECS连接RDS超时，连接池耗尽 | `alicloud-rds-ops` |
| T3+2min | SLB后端不可用，5xx爆发 | `alicloud-slb-ops` |

**诊断顺序:** SLB 5xx → ECS连接RDS超时 → 查VPC路由表 → 恢复路由
