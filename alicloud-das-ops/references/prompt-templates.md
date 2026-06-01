# DAS Troubleshooting Prompt Templates

## 使用说明

本文档按 **故障类型** 和 **排查阶段** 两个维度组织提示词模板。每个模板包含：
- **适用场景**：触发条件
- **输入变量**：需要填充的上下文
- **提示词模板**：可直接使用的结构化问法
- **预期输出**：Agent 应返回的内容格式
- **关键词索引**：便于快速检索的标签

---

## 一、按故障类型分类

### 1.1 连接超时 (connection_timeout)

#### 1.1.1 现象描述阶段

```markdown
## 提示词模板：连接超时现象采集

**适用场景**：用户报告数据库连接超时或连接失败

**输入变量**：
- {{user.instance_id}}: 数据库实例 ID
- {{user.engine}}: 数据库引擎类型
- {{user.symptom_description}}: 用户描述的症状
- {{user.time_range}}: 故障发生时间范围

**提示词**：
用户报告数据库实例 {{user.instance_id}} ({{user.engine}}) 出现连接问题：
"{{user.symptom_description}}"

请按以下步骤采集现象：
1. 调用 GetInstanceInspections 获取实例当前健康状态
2. 调用 GetSessionList 获取当前活跃会话列表，检查是否接近最大连接数
3. 调用 GetDBInstanceConnectivityDiagnosis 诊断网络连通性（如用户提供了源 IP）
4. 检查最近 1 小时的自治事件 (GetAutonomousNotifyEventsInRange)，查看是否有相关事件

请输出：
- 实例健康评分和关键指标
- 活跃会话数 / 最大连接数比率
- 网络连通性结果
- 相关自治事件列表
- 初步判断：连接问题属于哪一类（网络层 / 会话层 / 实例状态 / 配置层）

**关键词**：连接超时、连接失败、连接池、网络不通、会话满
```

#### 1.1.2 日志分析阶段

```markdown
## 提示词模板：连接超时日志分析

**适用场景**：已确认连接超时，需要分析根因

**输入变量**：
- {{data.inspection_score}}: 巡检评分
- {{data.session_count}}: 当前会话数
- {{data.max_connections}}: 最大连接数
- {{data.connectivity_result}}: 连通性诊断结果

**提示词**：
基于已采集的数据：
- 巡检评分：{{data.inspection_score}}
- 活跃会话：{{data.session_count}} / {{data.max_connections}}
- 连通性：{{data.connectivity_result}}

请执行以下分析：
1. 若 session_count / max_connections > 0.85：
   - 分析会话列表中是否存在长时间运行的慢查询（command = Sleep 且 time > 300s）
   - 检查是否有大量来自同一 IP 的连接（可能的连接池配置问题）
2. 若 connectivity_result = UNREACHABLE：
   - 解析 failureReason 和 suggestedActions
   - 判断是安全组、白名单还是网络路由问题
3. 若 inspection_score < 60：
   - 调用 CreateDiagnosticReport 生成诊断报告
   - 关注报告中与连接相关的部分

请输出：
- 根因概率排序（Top 3）
- 每个根因的证据链
- 建议的修复操作及风险等级

**关键词**：会话分析、连通性诊断、连接池溢出、慢查询阻塞
```

#### 1.1.3 根因定位阶段

```markdown
## 提示词模板：连接超时根因定位

**适用场景**：需要精确定位连接超时的根本原因

**输入变量**：
- {{data.fault_pattern_id}}: 匹配的故障模式 ID（如 F001, F006）
- {{data.evidence_chain}}: 已收集的证据链

**提示词**：
根据故障模式库匹配结果：{{data.fault_pattern_id}}

请执行根因定位决策树：
1. **检查实例注册状态**：
   - 若 API 返回 InvalidDBInstanceId.NotFound → 根因：实例未注册 (F006)
   - 修复：执行 AddHDMInstance

2. **检查实例运行状态**：
   - 若 inspection 返回 OperationDenied.InstanceStatus → 根因：实例状态异常
   - 修复：等待实例恢复或联系引擎技能检查实例状态

3. **检查连接数压力**：
   - 若 active_session_ratio > 0.85 → 根因：连接风暴 (F001)
   - 子判断：
     a. 若存在大量 Sleep 连接 → 连接池配置不当
     b. 若存在大量活跃慢查询 → 慢查询阻塞连接释放
     c. 若来自单一 IP 的连接过多 → 应用连接池溢出
   - 修复：CreateKillInstanceSessionTask（需用户确认）+ EnableSqlConcurrencyControl / CreateSqlLimitTask

4. **检查网络层**：
   - 若连通性诊断失败 → 根因：网络/安全策略问题
   - 修复：委托 alicloud-vpc-ops 检查安全组和白名单

请输出：
- 确定的根因及置信度（%）
- 根因证据摘要
- 修复方案及回滚策略

**关键词**：根因定位、决策树、置信度、证据链
```

#### 1.1.4 解决方案阶段

```markdown
## 提示词模板：连接超时解决方案

**适用场景**：已定位根因，需要执行修复并验证

**输入变量**：
- {{data.root_cause}}: 确定的根因
- {{data.fix_strategy}}: 修复策略
- {{user.confirmation}}: 用户确认（对于破坏性操作）

**提示词**：
根因已定位：{{data.root_cause}}
建议修复策略：{{data.fix_strategy}}

请按以下流程执行：
1. **安全门控检查**：
   - 若修复策略包含 CreateKillInstanceSessionTask → 必须获取用户显式确认
   - 若修复策略包含 EnableSqlConcurrencyControl / CreateSqlLimitTask → 必须确认 SQL 模式和限流参数

2. **执行修复**：
   - 按 fix_strategy 调用相应 API
   - 记录 RequestId 用于追踪

3. **验证修复**：
   - 修复后等待 30 秒
   - 重新调用 GetSessionList 检查会话数是否下降
   - 重新调用 GetInstanceInspections 检查评分是否回升
   - 若涉及网络修复，重新执行连通性诊断

4. **预防措施**：
   - 根据故障模式库中的 prevention 建议，输出长期预防方案

请输出：
- 修复执行结果（成功/失败）
- 验证结果（前后对比）
- 预防措施建议
- 是否需要升级至 DAS Pro 以获得自动处理能力

**关键词**：修复执行、安全门控、验证、预防措施
```

---

### 1.2 性能下降 (performance_degradation)

#### 1.2.1 现象描述阶段

```markdown
## 提示词模板：性能下降现象采集

**适用场景**：用户报告数据库响应慢、查询延迟增加、CPU 使用率高等性能问题

**输入变量**：
- {{user.instance_id}}: 数据库实例 ID
- {{user.engine}}: 数据库引擎类型
- {{user.performance_symptom}}: 性能症状描述（如"查询变慢"、"CPU 100%"）
- {{user.time_range}}: 故障时间范围

**提示词**：
用户报告数据库实例 {{user.instance_id}} ({{user.engine}}) 出现性能问题：
"{{user.performance_symptom}}"

请按以下步骤采集现象：
1. 调用 GetInstanceInspections 获取巡检评分和性能指标
2. 调用 GetQueryOptimizeData 获取查询治理数据（慢查询列表）
3. 调用 GetPfsSqlSamples 获取性能洞察 SQL 样本（需 Pro）
4. 调用 GetSessionList 检查是否有锁等待或长时间运行的会话
5. 调用 GetAutonomousNotifyEventsInRange 检查最近是否有 AUTO_SCALING 或 SQL_THROTTLING 事件

请输出：
- 巡检评分及趋势
- Top 10 慢查询（执行时间、频率、影响行数）
- 锁等待会话列表
- 自治事件摘要
- 初步判断：性能问题属于哪一类（慢查询 / 锁竞争 / 资源瓶颈 / 配置不当）

**关键词**：性能下降、查询慢、CPU 高、锁等待、慢查询
```

#### 1.2.2 日志分析阶段

```markdown
## 提示词模板：性能下降日志分析

**适用场景**：已确认性能下降，需要深入分析慢查询和资源配置

**输入变量**：
- {{data.inspection_score}}: 巡检评分
- {{data.slow_queries}}: 慢查询列表
- {{data.sql_samples}}: SQL 执行样本
- {{data.sessions}}: 会话列表

**提示词**：
基于已采集的性能数据：
- 巡检评分：{{data.inspection_score}}
- Top 慢查询：{{data.slow_queries}}
- SQL 样本：{{data.sql_samples}}

请执行以下分析：
1. **慢查询模式分析**：
   - 识别高频慢查询（出现次数 > 100 次/小时）
   - 分析执行计划变化（对比历史样本）
   - 检查是否缺少索引（关注全表扫描、filesort、临时表）

2. **锁竞争分析**：
   - 从 GetSessionList 中提取 state = "Waiting for lock" 或 "Locked" 的会话
   - 分析锁等待时间分布
   - 识别热点表/行

3. **资源瓶颈分析**：
   - 检查空间使用率（GetSpaceSummary）
   - 检查连接数使用率
   - 分析 I/O 等待比例（从 PFS 样本中提取）

4. **自治事件关联**：
   - 检查是否有 SQL_THROTTLING 事件（表明 DAS 已介入）
   - 检查 AUTO_SCALING 事件（资源是否已自动扩容）

请输出：
- 性能瓶颈 Top 3（按影响程度排序）
- 每个瓶颈的详细证据
- 优化建议（索引、SQL 改写、参数调优、扩容）

**关键词**：慢查询分析、执行计划、索引缺失、锁竞争、资源瓶颈
```

#### 1.2.3 根因定位阶段

```markdown
## 提示词模板：性能下降根因定位

**适用场景**：需要精确定位性能下降的根本原因

**输入变量**：
- {{data.bottleneck_type}}: 瓶颈类型
- {{data.fault_pattern_id}}: 匹配的故障模式 ID（如 F002）

**提示词**：
根据分析结果，瓶颈类型：{{data.bottleneck_type}}
匹配故障模式：{{data.fault_pattern_id}}

请执行根因定位：
1. **若瓶颈类型 = 慢查询**：
   - 检查执行计划是否劣化（对比历史 PFS 样本）
   - 检查统计信息是否过期
   - 检查数据量增长是否导致原有索引失效
   - 根因：F002（慢查询导致性能下降）

2. **若瓶颈类型 = 锁竞争**：
   - 检查事务隔离级别设置
   - 检查是否存在长事务
   - 检查是否有未提交的事务持有锁
   - 根因：事务粒度过大或隔离级别不当

3. **若瓶颈类型 = 资源瓶颈**：
   - 检查 CPU / 内存 / I/O 使用率
   - 检查是否有其他实例共享资源（如 ECS 上的自建库）
   - 根因：资源配置不足或资源争抢

4. **若瓶颈类型 = 配置不当**：
   - 检查缓冲池大小、连接池配置、查询缓存等参数
   - 根因：参数配置不适合当前工作负载

请输出：
- 确定的根因及置信度
- 根因证据摘要
- 修复优先级（P0/P1/P2）

**关键词**：根因定位、执行计划劣化、统计信息、长事务、资源配置
```

#### 1.2.4 解决方案阶段

```markdown
## 提示词模板：性能下降解决方案

**适用场景**：已定位性能瓶颈，需要执行优化

**输入变量**：
- {{data.root_cause}}: 根因
- {{data.optimization_plan}}: 优化计划
- {{user.approval}}: 用户审批（对于可能影响业务的操作）

**提示词**：
性能瓶颈根因：{{data.root_cause}}
优化计划：{{data.optimization_plan}}

请按以下流程执行：
1. **低风险优化（无需确认）**：
   - 生成 CreateDiagnosticReport 获取详细优化建议
   - 输出索引建议、SQL 改写建议

2. **中风险优化（需告知用户）**：
   - 若需要 EnableSqlConcurrencyControl / CreateSqlLimitTask 限流热点 SQL → 说明影响范围和持续时间
   - 若需要调整自动扩容配置 → 说明扩容触发条件和成本影响

3. **高风险优化（需用户确认）**：
   - 若需要杀会话（CreateKillInstanceSessionTask）→ 必须列出目标会话并获取确认
   - 若需要修改实例规格 → 说明重启窗口和影响

4. **验证优化效果**：
   - 优化后 5 分钟，重新调用 GetQueryOptimizeData 检查慢查询是否减少
   - 调用 GetInstanceInspections 检查评分是否回升
   - 持续监控 30 分钟，确认性能稳定

请输出：
- 已执行的优化操作及结果
- 优化前后性能对比
- 后续监控建议
- 是否需要 DAS Pro 的自动 SQL 优化功能

**关键词**：性能优化、SQL 限流、索引建议、自动扩容、效果验证
```

---

### 1.3 数据异常 (data_anomaly)

#### 1.3.1 现象描述阶段

```markdown
## 提示词模板：数据异常现象采集

**适用场景**：用户报告数据不一致、数据丢失、死锁、存储空间异常等

**输入变量**：
- {{user.instance_id}}: 数据库实例 ID
- {{user.engine}}: 数据库引擎类型
- {{user.anomaly_type}}: 异常类型（死锁 / 空间不足 / 数据不一致 / 主从延迟）
- {{user.time_range}}: 异常发生时间范围

**提示词**：
用户报告数据库实例 {{user.instance_id}} ({{user.engine}}) 出现数据异常：
类型：{{user.anomaly_type}}

请按以下步骤采集现象：
1. 调用 GetInstanceInspections 获取整体健康状态
2. 根据异常类型调用专项 API：
   - 死锁：CreateLatestDeadLockAnalysis + GetDeadLockHistory
   - 空间不足：GetSpaceSummary
   - 数据不一致：CreateDiagnosticReport（关注数据一致性检查）
   - 主从延迟：GetQueryOptimizeData（检查复制延迟相关指标）
3. 调用 GetAutonomousNotifyEventsInRange 检查相关自治事件
4. 调用 GetDasProServiceUsage 检查 Pro 存储配额（如使用 SQL Insight）

请输出：
- 异常现象详细描述
- 相关指标当前值
- 自治事件关联分析
- 初步判断：异常严重程度（warning / critical / emergency）

**关键词**：死锁、空间不足、数据不一致、主从延迟、存储配额
```

#### 1.3.2 日志分析阶段

```markdown
## 提示词模板：数据异常日志分析

**适用场景**：已确认数据异常，需要深入分析

**输入变量**：
- {{data.anomaly_type}}: 异常类型
- {{data.anomaly_data}}: 异常相关数据（死锁历史、空间使用情况等）

**提示词**：
异常类型：{{data.anomaly_type}}
异常数据：{{data.anomaly_data}}

请执行以下分析：
1. **死锁分析**：
   - 解析死锁图，识别参与死锁的表和事务
   - 分析死锁频率趋势（最近 7 天）
   - 识别死锁模式（是否总是同一组表）

2. **空间分析**：
   - 分析空间增长趋势（对比 7 天前数据）
   - 识别空间消耗 Top 3 的库/表
   - 检查是否有异常的大表或未清理的日志

3. **数据一致性分析**：
   - 分析诊断报告中的一致性检查结果
   - 检查主从复制状态（如适用）
   - 识别不一致的数据范围

请输出：
- 异常根因分析
- 影响范围评估
- 修复建议及风险等级

**关键词**：死锁分析、空间趋势、数据一致性、影响范围
```

#### 1.3.3 根因定位阶段

```markdown
## 提示词模板：数据异常根因定位

**适用场景**：需要精确定位数据异常根因

**输入变量**：
- {{data.anomaly_evidence}}: 异常证据
- {{data.fault_pattern_id}}: 匹配的故障模式（F003, F004, F005）

**提示词**：
根据证据和故障模式匹配：{{data.fault_pattern_id}}

请执行根因定位：
1. **若异常类型 = 死锁**：
   - 检查事务访问模式是否一致
   - 检查是否存在长事务持有锁
   - 根因：F004（死锁频繁）

2. **若异常类型 = 空间不足**：
   - 检查数据文件增长速率
   - 检查 Binlog/Redo log 保留策略
   - 检查临时表空间使用情况
   - 根因：F003（存储空间不足）

3. **若异常类型 = 存储配额耗尽**：
   - 检查 DAS Pro 存储使用趋势
   - 检查 SQL Insight 数据保留期
   - 根因：F005（DAS Pro 存储配额耗尽）

请输出：
- 确定的根因及置信度
- 根因证据链
- 修复优先级

**关键词**：死锁根因、空间增长、存储配额、证据链
```

#### 1.3.4 解决方案阶段

```markdown
## 提示词模板：数据异常解决方案

**适用场景**：已定位数据异常根因，需要修复

**输入变量**：
- {{data.root_cause}}: 根因
- {{data.fix_plan}}: 修复计划
- {{user.confirmation}}: 用户确认

**提示词**：
数据异常根因：{{data.root_cause}}
修复计划：{{data.fix_plan}}

请按以下流程执行：
1. **死锁修复**：
   - 输出事务优化建议（访问顺序统一、缩短事务）
   - 如需临时缓解，可创建 SQL 限流（EnableSqlConcurrencyControl / CreateSqlLimitTask）降低并发
   - 持续监控死锁频率

2. **空间修复**：
   - 检查是否可配置自动扩容（SetAutoScalingConfig）
   - 输出空间清理建议（清理 Binlog、归档历史数据、删除临时文件）
   - 如需紧急扩容，说明操作步骤和影响

3. **配额修复**：
   - 检查存储配额使用情况
   - 建议升级配额或配置自动清理
   - 配置告警（SetEventSubscription）防止再次耗尽

4. **验证**：
   - 修复后重新检查相关指标
   - 确认异常是否消除
   - 输出长期预防建议

请输出：
- 修复执行结果
- 验证结果
- 预防措施

**关键词**：死锁修复、空间清理、自动扩容、配额管理、验证
```

---

## 二、按排查阶段分类

### 2.1 现象描述阶段 (symptom_collection)

```markdown
## 通用提示词模板：现象采集框架

**适用场景**：任何故障的初始阶段，需要系统化采集现象

**输入变量**：
- {{user.issue_description}}: 用户问题描述
- {{user.instance_id}}: 实例 ID
- {{user.engine}}: 引擎类型
- {{user.impact_scope}}: 影响范围（单实例 / 多实例 / 全业务）

**提示词**：
用户报告问题："{{user.issue_description}}"
影响范围：{{user.impact_scope}}

请按 **5W2H** 框架采集现象：
1. **What**：什么现象？（错误码、延迟、失败率）
2. **When**：何时发生？（首次发生时间、频率、持续时间）
3. **Where**：影响范围？（实例、库、表、应用）
4. **Who**：谁受影响？（应用、用户、服务）
5. **Why**：可能原因？（变更、流量、配置）
6. **How**：如何表现？（指标变化、日志特征）
7. **How much**：影响程度？（QPS 下降比例、错误率）

请调用以下 API 采集基础数据：
1. GetInstanceInspections — 获取健康评分
2. GetAutonomousNotifyEventsInRange — 获取自治事件
3. 根据症状调用专项 API（见故障类型分类）

请输出：
- 结构化现象摘要（按 5W2H）
- 关键指标当前值
- 初步分类（connection_timeout / performance_degradation / data_anomaly）
- 下一步排查方向

**关键词**：现象采集、5W2H、初始诊断、问题分类
```

### 2.2 日志分析阶段 (log_analysis)

```markdown
## 通用提示词模板：结构化日志分析

**适用场景**：已采集日志/API 数据，需要进行结构化分析

**输入变量**：
- {{data.api_responses}}: API 返回数据集合
- {{data.time_range}}: 分析时间范围
- {{data.baseline}}: 历史基线数据（如有）

**提示词**：
请对以下 API 返回数据进行结构化分析：
数据：{{data.api_responses}}
时间范围：{{data.time_range}}
历史基线：{{data.baseline}}

请按以下层次分析：
1. **信号提取**：
   - 错误信号：Code != 200 或 Success == false
   - 性能信号：inspection score < 60, 慢查询突增, 活跃会话 > 阈值
   - 资源信号：空间使用率 > 85%, 存储配额接近上限
   - 事件信号：自治事件包含 AUTO_SCALING, SQL_THROTTLING, SPACE_OPTIMIZATION

2. **时序关联**：
   - 对比当前值与基线，识别异常偏离
   - 关联同一时间段内的多个异常信号
   - 识别异常的起始时间和持续时间

3. **模式匹配**：
   - 将当前症状与故障模式库（fault_patterns）匹配
   - 输出匹配的故障模式 ID 及匹配度

4. **证据链构建**：
   - 按时间顺序排列关键证据
   - 标注每个证据的来源 API 和字段路径
   - 评估证据的可靠性

请输出：
- 异常信号列表（按优先级排序）
- 时序关联分析结果
- 匹配的故障模式及匹配度
- 证据链摘要

**关键词**：日志分析、信号提取、时序关联、模式匹配、证据链
```

### 2.3 根因定位阶段 (root_cause_identification)

```markdown
## 通用提示词模板：根因定位决策树

**适用场景**：已分析日志，需要系统性地定位根因

**输入变量**：
- {{data.evidence_chain}}: 证据链
- {{data.fault_patterns}}: 匹配的故障模式列表
- {{data.symptom_category}}: 症状分类

**提示词**：
基于证据链和故障模式匹配结果，请执行根因定位：

**阶段 1：排除法**
1. 检查是否为已知故障模式（匹配度 > 80%）
2. 检查是否为 DAS 服务问题（InvalidDBInstanceId.NotFound → 实例未注册）
3. 检查是否为实例状态问题（OperationDenied.InstanceStatus → 实例不稳定）
4. 检查是否为配额/余额问题（InsufficientBalance → 账户问题）

**阶段 2：深度分析**
1. 若匹配故障模式 → 按模式中的 diagnostic_apis 顺序深入验证
2. 若未匹配 → 扩大诊断范围，调用 CreateDiagnosticReport 生成综合报告
3. 若涉及跨产品 → 按 delegation 规则委托给对应技能（alicloud-rds-ops, alicloud-vpc-ops 等）

**阶段 3：根因确认**
1. 列出所有可能的根因（Top 3）
2. 为每个根因标注置信度（基于证据支持度）
3. 排除与证据矛盾的根因
4. 确认最可能的根因

请输出：
- 根因定位过程（决策路径）
- 确定的根因及置信度
- 排除的其他可能性及原因
- 修复建议及风险等级

**关键词**：根因定位、决策树、排除法、置信度、跨技能委托
```

### 2.4 解决方案阶段 (resolution)

```markdown
## 通用提示词模板：修复执行与验证

**适用场景**：已定位根因，需要执行修复并验证

**输入变量**：
- {{data.root_cause}}: 根因
- {{data.recommended_fixes}}: 建议修复方案
- {{user.risk_acceptance}}: 用户风险接受度（保守 / 平衡 / 激进）

**提示词**：
根因：{{data.root_cause}}
建议修复方案：{{data.recommended_fixes}}
用户风险接受度：{{user.risk_acceptance}}

请按以下流程执行：

**阶段 1：修复策略选择**
- 保守：优先选择无影响的修复（如配置调整、限流）
- 平衡：选择影响可控的修复（如杀会话、扩容）
- 激进：选择快速恢复但可能有影响的修复（如重启、强制清理）

**阶段 2：安全门控**
1. 检查修复操作是否需要用户确认（破坏性操作）
2. 列出所有受影响的会话/连接/数据
3. 评估修复操作的回滚难度
4. 获取用户确认（如需要）

**阶段 3：执行修复**
1. 按优先级顺序执行修复操作
2. 记录每个操作的 RequestId
3. 监控操作执行状态

**阶段 4：验证修复**
1. 修复后立即检查关键指标
2. 持续监控 5-30 分钟（根据故障类型）
3. 对比修复前后的指标变化
4. 确认故障是否完全消除

**阶段 5：复盘与预防**
1. 总结故障处理过程
2. 输出预防措施建议
3. 如需，配置告警规则（SetEventSubscription）
4. 更新故障模式库（如有新发现）

请输出：
- 修复策略及选择理由
- 执行结果（成功/失败/部分成功）
- 验证结果（前后对比）
- 预防措施
- 故障处理时间线

**关键词**：修复执行、安全门控、验证、复盘、预防措施
```

---

## 三、关键词索引

### 按故障类型索引

| 关键词 | 故障类型 | 相关提示词 |
|--------|----------|------------|
| 连接超时 | connection_timeout | 1.1.1 - 1.1.4 |
| 连接失败 | connection_timeout | 1.1.1, 1.1.3 |
| 连接池 | connection_timeout | 1.1.2, 1.1.3 |
| 会话满 | connection_timeout | 1.1.1, 1.1.3 |
| 网络不通 | connection_timeout | 1.1.1, 1.1.3 |
| 性能下降 | performance_degradation | 1.2.1 - 1.2.4 |
| 查询慢 | performance_degradation | 1.2.1, 1.2.2 |
| CPU 高 | performance_degradation | 1.2.1, 1.2.2 |
| 锁等待 | performance_degradation | 1.2.2, 1.2.3 |
| 慢查询 | performance_degradation | 1.2.1 - 1.2.4 |
| 死锁 | data_anomaly | 1.3.1 - 1.3.4 |
| 空间不足 | data_anomaly | 1.3.1 - 1.3.4 |
| 数据不一致 | data_anomaly | 1.3.1, 1.3.2 |
| 存储配额 | data_anomaly | 1.3.1, 1.3.3, 1.3.4 |
| 主从延迟 | data_anomaly | 1.3.1 |

### 按排查阶段索引

| 关键词 | 排查阶段 | 相关提示词 |
|--------|----------|------------|
| 现象采集 | symptom_collection | 2.1, 1.1.1, 1.2.1, 1.3.1 |
| 5W2H | symptom_collection | 2.1 |
| 日志分析 | log_analysis | 2.2, 1.1.2, 1.2.2, 1.3.2 |
| 信号提取 | log_analysis | 2.2 |
| 时序关联 | log_analysis | 2.2 |
| 模式匹配 | log_analysis | 2.2 |
| 根因定位 | root_cause_identification | 2.3, 1.1.3, 1.2.3, 1.3.3 |
| 决策树 | root_cause_identification | 2.3, 1.1.3 |
| 置信度 | root_cause_identification | 2.3, 1.1.3 |
| 修复执行 | resolution | 2.4, 1.1.4, 1.2.4, 1.3.4 |
| 安全门控 | resolution | 2.4, 1.1.4 |
| 验证 | resolution | 2.4, 1.1.4 |
| 预防措施 | resolution | 2.4, 1.1.4 |

### 按操作类型索引

| 关键词 | 相关 API | 提示词位置 |
|--------|----------|------------|
| 巡检 | GetInstanceInspections | 全阶段 |
| 诊断报告 | CreateDiagnosticReport | 1.2.2, 1.3.1 |
| 会话管理 | GetSessionList, CreateKillInstanceSessionTask | 1.1.1, 1.1.3, 1.1.4 |
| SQL 限流 | CreateSqlLimitTask, DescribeSqlLimitTasks, EnableSqlConcurrencyControl, DisableSqlConcurrencyControl, DisableAllSqlConcurrencyControlRules, GetRunningSqlConcurrencyControlRules, GetSqlConcurrencyControlRulesHistory, GetSqlConcurrencyControlKeywordsFromSqlText | 1.1.4, 1.2.4 |
| 空间分析 | GetSpaceSummary | 1.3.1, 1.3.2 |
| 死锁分析 | CreateLatestDeadLockAnalysis, GetDeadLockHistory | 1.3.1, 1.3.2 |
| 性能洞察 | GetPfsSqlSamples, GetQueryOptimizeData | 1.2.1, 1.2.2 |
| 自治事件 | GetAutonomousNotifyEventsInRange | 全阶段 |
| 自动扩容 | SetAutoScalingConfig, GetAutoScalingConfig | 1.2.4, 1.3.4 |
| 连通性诊断 | GetDBInstanceConnectivityDiagnosis | 1.1.1, 1.1.3 |
| 实例注册 | AddHDMInstance | 1.1.3 |
| 事件订阅 | SetEventSubscription, GetEventSubscription | 1.3.4 |
| Pro 配额 | GetDasProServiceUsage | 1.3.1, 1.3.3 |

---

## 四、快速查询示例

### 示例 1：通过关键词查询

**用户输入**："连接超时怎么排查？"

**匹配过程**：
1. 关键词匹配："连接超时" → 故障类型 connection_timeout
2. 阶段判断：用户未指定阶段，默认从现象描述开始
3. 返回提示词：1.1.1（现象描述）+ 2.1（通用现象采集框架）

### 示例 2：通过阶段查询

**用户输入**："我已经知道是慢查询导致的，怎么定位根因？"

**匹配过程**：
1. 关键词匹配："慢查询" → 故障类型 performance_degradation
2. 阶段判断："定位根因" → root_cause_identification
3. 返回提示词：1.2.3（根因定位）+ 2.3（通用根因定位决策树）

### 示例 3：通过 API 查询

**用户输入**："GetSessionList 返回很多连接，怎么办？"

**匹配过程**：
1. API 匹配：GetSessionList → 会话管理 / 连接问题
2. 症状推断："很多连接" → 连接风暴或连接池问题
3. 返回提示词：1.1.2（日志分析）+ 1.1.3（根因定位）

### 示例 4：复合故障查询

**用户输入**："实例评分很低，而且空间快满了"

**匹配过程**：
1. 多关键词匹配："评分很低" → performance_degradation；"空间快满" → data_anomaly
2. 关联分析：可能是慢查询导致临时表空间膨胀
3. 返回提示词：1.2.1（性能现象采集）+ 1.3.1（数据异常现象采集）+ 2.2（日志关联分析）
