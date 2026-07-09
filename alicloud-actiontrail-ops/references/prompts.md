# ActionTrail Operations — AIOps Prompts Handbook

> **Purpose:** 25+ categorized prompt examples for ActionTrail with AIOps focus.

## 审计事件查询

1."查看最近 1 小时的 Delete 系列操作"
2."查询用户 xxx 在某个时间窗口的所有操作"
3."查看 Root 账户的登录历史"
4."查询某个 AK 创建后的所有操作"

## Insight 告警示例

5."查看 IpInsight 触发的事件"
6."分析 API 错误率突增的 Insight 事件"
7."有 TrailConcealmentInsight 事件吗？"
8."查看 PolicyChangeInsight 事件详情"

## 安全诊断类

9."检测到用户 IP 异常，帮我追踪后续所有操作"
10."AK 被盗用，帮我分析这个 AK 的所有操作链"
11."权限被篡改，帮我追踪是谁修改的"
12."Trail 被禁用，帮我追查原因"

## 多指标关联巡检

13."执行 ActionTrail 多指标巡检，检查异常审计事件"
14."检查是否存在 AK 滥用模式"
15."巡检所有用户的权限变更记录"
16."审计 Trail 投递是否正常"

## 告警风暴处理

17."多个 Insight 事件同时触发，帮我聚合分析"
18."发现疑似攻击链，帮我从 ActionTrail 追踪全貌"
19."审计事件量突增，帮我分析根因"

## 跨 Skill 协同诊断

20."ECS 实例被删除了，帮我通过 ActionTrail 追踪谁操作的"
21."SLB 配置被修改，帮我审计变更历史"
22."RDS 被删除，帮我查操作者和时间"
23."多个资源同时异常，ActionTrail 是否有发现？"

## 主动巡检

24."对所有 Trail 执行主动巡检"
25."生成审计巡检报告，包括 Trail 状态和 Insight 事件"
26."巡检所有用户的权限变更，识别异常模式"

## 可观测性联动

27."审计事件异常，帮我查 SLS 中的操作日志"
28."IP 事件触发了，帮我查 FlowLog 确认来源"
29."策略变更事件，帮我查 RAM 详情"

## 自愈操作

30."帮我自动重新启用被禁用的 Trail"
31."帮我审计并回滚最近的安全策略变更"
32."帮我禁用可疑的 AK"
