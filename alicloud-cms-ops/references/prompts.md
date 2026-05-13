# CMS AIOps 常用提示词手册

> 本手册整理了 `alicloud-cms-ops` Skill 的常用提示词（Prompts），便于 Agent 快速理解和执行各类监控运维任务。

---

## 一、指标查询类

### 1.1 查询单个指标最新值

```
查询 {{user.instance_id}} 的最新 {{user.metric_name}} 指标值，
命名空间为 {{user.namespace}}，地域 {{user.region}}。
```

### 1.2 查询指标历史趋势

```
查询 {{user.instance_id}} 在过去 {{user.duration}} 内的 {{user.metric_name}} 趋势，
命名空间 {{user.namespace}}，聚合周期 {{user.period}} 秒。
```

### 1.3 批量查询多指标

```
对 {{user.instance_id}} 执行多指标关联巡检，
查询命名空间 {{user.namespace}} 下的所有关键指标（CPU、内存、磁盘、网络），
识别是否存在复合异常模式。
```

### 1.4 对比多个实例指标

```
对比以下实例的 {{user.metric_name}} 指标：{{user.instance_ids}}，
命名空间 {{user.namespace}}，找出指标异常的实例。
```

---

## 二、告警管理类

### 2.1 创建告警规则

```
为 {{user.instance_id}} 创建一条 {{user.metric_name}} 告警规则，
规则名称 {{user.alarm_name}}，阈值 {{user.threshold}}，
比较运算符 {{user.comparison_operator}}，统计周期 {{user.period}} 秒，
连续 {{user.evaluation_count}} 个周期触发后告警，
通知联系组 {{user.contact_group}}。
```

### 2.2 列出活跃告警

```
列出 {{user.region}} 当前所有状态为 ALARM 的告警规则，
按命名空间 {{user.namespace}} 过滤。
```

### 2.3 检查告警规则配置

```
检查告警规则 {{user.alarm_name}} 的配置是否正确，
包括阈值、统计方法、维度、通知方式等。
```

### 2.4 删除告警规则

```
删除告警规则 {{user.alarm_name}}，
删除前确认该规则不再使用。
```

---

## 三、多指标关联巡检类

### 3.1 执行多指标异常巡检

```
对 {{user.instance_id}} 执行多指标关联异常巡检，
命名空间 {{user.namespace}}，地域 {{user.region}}。
检测以下异常模式：
- CPU-Memory 压力
- Disk-IO 瓶颈
- Load-CPU 不匹配
- 连接耗尽
- 内存泄漏趋势
- CPU 突增
```

### 3.2 分析指标关联性

```
分析 {{user.instance_id}} 在过去 1 小时内的多指标关联性，
重点关注 CPUUtilization、MemoryUsage、LoadAverage、DiskUsage 的相关性，
判断是否存在资源竞争或 IO 等待问题。
```

### 3.3 趋势异常检测

```
检测 {{user.instance_id}} 的 {{user.metric_name}} 指标趋势，
判断是否存在单调上升/下降、周期性异常或突发波动。
```

---

## 四、告警驱动诊断类

### 4.1 告警触发后的根因诊断

```
CMS 告警 {{user.alarm_name}} 已触发，
资源 {{user.instance_id}}，指标 {{user.metric_name}}，当前值 {{user.metric_value}}。

执行以下诊断流程：
1. 验证告警有效性（查询最新指标值）
2. 检查资源状态（委托对应产品 Skill）
3. 执行多指标关联分析
4. 如为数据库告警，委托 DAS 进行 AI 诊断
5. 检查关联告警（过去 1 小时内同一资源的其他告警）
6. 生成统一诊断报告
```

### 4.2 跨 Skill 诊断编排

```
告警来源：{{user.namespace}} / {{user.metric_name}}
资源 ID：{{user.instance_id}}

根据 Alarm-to-Diagnosis 委托矩阵：
1. 确定主诊断 Skill 和次诊断 Skill
2. 依次调用各 Skill 获取资源状态和诊断信息
3. 汇总所有 Skill 的输出，生成统一诊断报告
4. 给出根因判断和修复建议
```

### 4.3 级联故障诊断

```
检测到多个告警在短时间内触发：
{{user.alarm_list}}

执行级联故障诊断：
1. 按时间排序告警
2. 识别最早的告警（可能的根因）
3. 分析资源依赖关系
4. 判断后续告警是否为级联影响
5. 生成级联故障分析报告
```

---

## 五、主动巡检类

### 5.1 执行定时巡检

```
对监控组 {{user.group_id}} 执行主动巡检：
1. 列出组内所有资源
2. 采集各资源的关键指标
3. 应用静态阈值和趋势分析检测异常
4. 对异常资源执行跨 Skill 诊断
5. 生成巡检报告
```

### 5.2 巡检报告生成

```
生成 {{user.group_id}} 监控组的巡检报告，包含：
- 资源清单及健康状态
- 异常资源及异常模式
- 已委托的诊断 Skill 及发现
- 修复建议
- 趋势预测（如有）
```

### 5.3 巡检异常处理

```
巡检发现以下异常：
{{user.anomaly_list}}

对每个异常执行：
1. 确认异常严重程度
2. 委托对应 Skill 深入诊断
3. 获取诊断结果
4. 给出修复建议
5. 如需立即处理，通知运维人员
```

---

## 六、告警风暴处理类

### 6.1 检测告警风暴

```
检测过去 5 分钟内是否存在告警风暴：
1. 查询所有状态为 ALARM 的告警
2. 统计告警数量
3. 按资源和命名空间聚合
4. 判断是否符合风暴检测标准
5. 如检测到风暴，进入风暴处理模式
```

### 6.2 告警聚合分析

```
对以下告警进行聚合分析：
{{user.alarm_list}}

执行：
1. 按资源 ID 分组
2. 按命名空间分组
3. 识别级联模式
4. 确定根告警
5. 抑制非根告警的通知
6. 对根告警执行深度诊断
```

### 6.3 风暴后复盘

```
告警风暴已平息，执行复盘：
1. 汇总风暴期间的所有告警
2. 分析根因
3. 评估诊断和修复效果
4. 更新知识库
5. 提出预防措施建议
```

---

## 七、DAS 联动诊断类

### 7.1 数据库告警联动 DAS

```
数据库告警 {{user.alarm_name}} 触发，
实例 {{user.instance_id}}，引擎 {{user.engine}}。

委托 DAS 执行以下诊断：
1. GetInstanceInspections 获取健康评分
2. CreateDiagnosticReport 生成性能诊断报告
3. 如涉及连接问题，执行 CreateLatestDeadLockAnalysis
4. 获取慢查询和 SQL 优化建议
5. 将 DAS 诊断结果纳入统一报告
```

### 7.2 DAS 诊断结果解读

```
DAS 诊断报告已返回：
{{user.das_report}}

解读报告并提取关键信息：
1. 健康评分及变化趋势
2. 发现的异常和瓶颈
3. SQL 优化建议
4. 索引建议
5. 将关键发现转化为可执行的修复建议
```

---

## 八、知识库应用类

### 8.1 匹配故障模式

```
当前告警：
- 命名空间：{{user.namespace}}
- 指标：{{user.metric_name}}
- 资源：{{user.instance_id}}
- 当前值：{{user.metric_value}}

在知识库中匹配故障模式：
1. 根据 namespace + metric 查找对应 Pattern
2. 检查关联指标是否符合 Pattern 特征
3. 如匹配成功，按 Pattern 的诊断步骤执行
4. 如未匹配，执行通用诊断流程并记录新 Pattern
```

### 8.2 更新知识库

```
故障已处理，更新知识库：
- 告警：{{user.alarm_name}}
- 根因：{{user.root_cause}}
- 修复方案：{{user.solution}}
- 预防措施：{{user.prevention}}

如与现有 Pattern 匹配，更新该 Pattern；
如不匹配，创建新 Pattern。
```

---

## 九、可观测性联动类

### 9.1 Metrics → Logs 联动

```
CMS 告警 {{user.alarm_name}} 触发，
需要关联 SLS 日志进行根因分析。

执行：
1. 确定告警时间窗口
2. 查询对应 SLS Project/Logstore
3. 使用查询语句检索异常日志
4. 关联日志时间戳和 CMS 指标时间戳
5. 判断日志异常是否与指标异常相关
6. 将日志发现纳入诊断报告
```

### 9.2 Metrics → Traces 联动

```
CMS 告警 {{user.alarm_name}} 触发，
需要关联 ARMS 链路追踪进行性能分析。

执行：
1. 确定告警时间窗口
2. 查询 ARMS 慢调用 Trace
3. 识别耗时最长的 Span
4. 关联该 Span 的服务和 CMS 指标
5. 判断是否为性能瓶颈根因
6. 将 Trace 分析纳入诊断报告
```

### 9.3 三位一体诊断

```
执行 Metrics + Logs + Traces 三位一体诊断：
1. Metrics（CMS）：确认指标异常及趋势
2. Logs（SLS）：检索异常日志，定位错误源
3. Traces（ARMS）：追踪慢调用链路，定位瓶颈
4. 关联三者发现，生成统一根因报告
5. 给出修复建议和预防措施
```

---

## 十、报告生成类

### 10.1 统一诊断报告

```
生成统一诊断报告，包含以下字段：
- report_id: 报告唯一标识
- timestamp: 诊断时间
- alarm_source: 原始告警信息
- resource_id: 资源 ID
- resource_status: 资源状态
- metric_value: 指标当前值
- metric_trend: 指标趋势分析
- anomaly_patterns: 检测到的异常模式
- deep_diagnosis: DAS 深度诊断结果
- correlated_alarms: 关联告警
- correlated_events: 关联事件
- root_cause: 根因判断
- recommendation: 修复建议
- delegated_skills: 已委托的 Skill 列表
```

### 10.2 巡检报告

```
生成巡检报告，包含：
- 巡检时间范围
- 巡检资源范围
- 各资源健康状态汇总
- 异常资源详情
- 异常模式识别结果
- 已执行的诊断操作
- 修复建议
- 下次巡检建议
```

### 10.3 复盘报告

```
生成故障复盘报告，包含：
- 故障时间线
- 告警触发过程
- 诊断执行过程
- 根因分析
- 修复过程
- 影响评估
- 改进建议
- 知识库更新内容
```

---

## 十一、通用运维类

### 11.1 监控大盘配置

```
为 {{user.group_id}} 监控组配置监控大盘：
1. 列出组内所有资源
2. 为每类资源配置关键指标图表
3. 配置告警规则
4. 配置通知方式
```

### 11.2 告警规则优化

```
优化 {{user.alarm_name}} 告警规则：
1. 分析历史告警数据
2. 评估当前阈值的合理性
3. 调整阈值减少误报/漏报
4. 优化 EvaluationCount
5. 优化通知策略
```

### 11.3 容量规划建议

```
基于 {{user.instance_id}} 的历史指标数据，
分析 {{user.metric_name}} 的趋势，
给出容量规划建议：
1. 当前资源使用率
2. 增长趋势预测
3. 预计达到阈值的时间
4. 扩容建议（规格、时间）
```

---

## 十二、提示词使用技巧

### 12.1 变量替换

所有 `{{user.xxx}}` 和 `{{env.xxx}}` 为占位符，实际使用时替换为具体值：
- `{{user.instance_id}}` → `i-bp1xxxxxxxxxxxxxx`
- `{{user.namespace}}` → `acs_ecs_dashboard`
- `{{user.region}}` → `cn-hangzhou`

### 12.2 组合使用

提示词可以组合使用，例如：
```
1. 先执行"查询单个指标最新值"确认告警
2. 再执行"告警触发后的根因诊断"进行深度分析
3. 最后执行"统一诊断报告"生成报告
```

### 12.3 条件分支

根据执行结果选择不同提示词：
- 如果指标正常 → 使用"检查告警规则配置"
- 如果指标异常 → 使用"告警触发后的根因诊断"
- 如果多个告警 → 使用"级联故障诊断"

### 12.4 输出格式

要求 Agent 按指定格式输出：
```
请按以下格式输出诊断结果：

## 诊断摘要
（一句话概括）

## 详细发现
（分点列出）

## 根因判断
（明确根因）

## 修复建议
（可执行的操作）

## 风险评估
（不修复的后果）
```
