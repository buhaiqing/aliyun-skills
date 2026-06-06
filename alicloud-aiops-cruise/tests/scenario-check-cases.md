# 场景验证案例

> 用于测试和验证 `alicloud-aiops-cruise` 的各种巡检场景。
> 每个 Case 包含: 输入条件 → 期望行为 → 验证路径。

## Phase 1: 前置交互验证

| Case ID | 描述 | 输入 | 期望行为 | 验证方式 |
|---|---|---|---|---|
| P0-01 | 无客户标识 | 跳过客户名直接开始 | 拒绝执行，要求输入客户标签 | 对话交互 |
| P0-02 | 无效 AK/SK | ALIBABA_CLOUD_ACCESS_KEY_ID 为空 | 报错 HALT，提示配置凭证 | 执行 `test -n "$AK_ID"` |
| P0-03 | 客户标签搜索无结果 | 客户名在阿里云无对应标签 | 输出"无资源"，退出 | ResourceCenter 返回空列表 |

## Phase 2: 拓扑发现验证

| Case ID | 描述 | 期望行为 | 验证方式 |
|---|---|---|---|
| P1-01 | 单 VPC 多 ECS | 正确映射 VPC→vSwitch→ECS 关系 | `aliyun vpc DescribeVpcs` + `DescribeInstances` 交叉验证 |
| P1-02 | SLB 有后端但无数据 | SLB 在拓扑中但无后端 ECS | DescribeVServerGroups 返回空 → 标记"SLB 无后端" |
| P1-03 | 跨区域资源 | 客户标签在多个区域有资源 | — 先在一个区域执行，用户确认后再扫其他区域 |
| P1-04 | EIP 绑定/未绑定 | EIP 列表显示绑定状态 | DescribeEipAddresses 的 InstanceId 字段 |

## Phase 3: 监控采集验证

| Case ID | 描述 | 期望行为 | 验证方式 |
|---|---|---|---|
| P2-01 | ECS 监控指标有数据 | 返回 CPU/内存/IOPS 等数值 | `aliyun cms DescribeMetricList` 返回 ≥1 个 datapoint |
| P2-02 | 新创建 ECS 尚无监控数据 | 返回空数组，跳过该指标 | jq 判断 `length == 0` → skip |
| P2-03 | 环比计算正确 | 当前值 > 昨日同期 30% → Warning | 手动计算验证 |
| P2-04 | DAS 可用/不可用 | DAS 启用 → 返回慢 SQL；未启用 → 提示"未开启 DAS 专业版" | DAS Go SDK 返回 |

## Phase 4: 推理规则验证

| Case ID | 描述 | 期望行为 | 验证方式 |
|---|---|---|---|
| P3-01 | SLB 健康检查失败 + ECS 正常 | 匹配 SLB-ECS-01 → 查网络连通性 | 对照 inference-rules.md |
| P3-02 | ECS CPU + 内存双高 | 匹配 ECS-01 → 查进程 TOP | 对照 inference-rules.md |
| P3-03 | RDS CPU + 慢查询双高 | 匹配 RDS-01 → DAS 慢 SQL | 对照 inference-rules.md |
| P3-04 | 全链路正常 | 无规则匹配 → 输出"无异常" | 对照 inference-rules.md |
| P3-05 | 0.0.0.0/0 开放数据库端口 | 匹配 SG-02 → Critical | 对照 inference-rules.md |

## 端到端验收

| Case ID | 场景 | 期望输出 |
|---|---|---|
| E2E-01 | 日常巡检（5台ECS+2SLB+1RDS+1Redis） | 完整 Markdown 报告 + JSON 持久化 |
| E2E-02 | 故障排查（用户报"系统慢"） | 根因报告含链路追踪 + 建议 |
| E2E-03 | 容量规划（磁盘增长趋势 + 30天预测） | 趋势预测表 + 达阈值日期 |
| E2E-04 | 大促预检（3x 流量模拟） | 升配建议列表 + 优先级排序 |