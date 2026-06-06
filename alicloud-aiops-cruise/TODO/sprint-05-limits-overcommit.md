# Sprint 5: ACK 节点 Limits 超分检测（P0）

> **业务价值**: 发现 K8s 集群中最常见也最隐蔽的风险——Pod Limits 总和超过节点 Capacity，高负载下必然触发 CPU Throttling / OOM，且 Developer 通常不知情
> **交付物**: `runbooks/scripts/_shared.py` (ACK 注册表) + 4 个 runbook 脚本 ACK 模块同步增强
> **前置条件**: 无（独立推进，不依赖其他 Sprint）
> **关联验收项**: S1-D7

### 数据源

| 数据源 | 指标 | 维度 | 作用 |
|--------|------|------|------|
| CMS `acs_k8s` | `node.cpu.capacity`, `node.cpu.limit` | userId,cluster,node | 算 CPU Limits 超卖比 |
| CMS `acs_k8s` | `node.memory.capacity`, `node.memory.limit` | userId,cluster,node | 算内存 Limits 超卖比 |
| CMS `acs_k8s` | `node.cpu.usage_rate`, `node.cpu.request` | userId,cluster,node | 辅助判断（usage vs limit） |
| CMS `acs_k8s` | `pod.cpu.limit`, `pod.cpu.request`, `pod.cpu.usage_rate` | userId,cluster,namespace,type,app,pod | 钻取到 Pod 级明细 |
| CS API | `DescribeClusterNodePools` | clusterId | 节点池信息，关联到业务 |

### 任务

- [x] **5.1** `_shared.py` ACK 产品注册表：增加 `acs_k8s` 命名空间 + 节点级指标映射（capacity/limit/usage_rate/request）
- [x] **5.2** `_shared.py` 新增 `_collect_k8s_limits()` 函数：按节点聚合查询 node.cpu.{capacity,limit} + node.memory.{capacity,limit}
- [x] **5.3** `_shared.py` 新增 `_drill_pod_limits()` 函数：对超分节点钻取 Pod 级 limit/usage，排序出 Top 5
- [x] **5.4** `daily-health-check.py` ACK 全集成：
  - [x] `_collect_ack()` 独立采集器（集群级+节点级+7天回溯+SLS嗅探+Limits超分检测）
  - [x] `collect_and_score()` 分发 ACK → `_collect_ack()`
  - [x] `report()` 接受并输出 ACK 报告章节（回溯+SLS状态+Limits超分）
  - [x] `main()` 传递 ack_data
  - [x] Ruff Lint 零错误通过
  - [x] Limits 超分检测集成（`_collect_k8s_limits()` + `format_limits_report()`）
- [x] **5.5** `_shared.py` 新增 `backtrack_cms()` 回溯函数：支持双模式（回溯 N 天 / 指定时段）
- [x] **5.6** `_shared.py` 新增 `check_audit_log_enabled()` + `query_sls_k8s_events()` SLS 嗅探与查询
- [x] **5.7** `_shared.py` 新增 `format_backtrack_report()` 回溯报告格式化函数
- [x] **5.8** `threshold-definitions.md` 增加 Limits 超卖比阈值定义
- [x] **5.9** `inference-rules.md` 增加 Limits 超分推理规则（含修复建议链路）
- [x] **5.10** `references/history-backtracking.md` 三层回溯方案文档
- [x] **5.11** 集成测试：6 个用例全部通过（TC-01~TC-06）
- [x] **5.12** CloudAssistant + kubectl events POC — **已完成，结论见下方**
  - [x] 验证 `DescribeClusterUserKubeconfig` 获取 kubeconfig 可行性 — ✅ **可行**，API 成功返回
  - [x] 验证 CloudAssistant `RunCommand` 执行可行性 — ❌ **被 RAM 拒绝**（缺少 `ecs:RunCommand` 权限）
  - [x] 验证本地 kubectl + kubeconfig 执行只读命令 — ❌ **被 RBAC 拒绝**（当前子账号在集群内无角色绑定）
  - [x] 确认 K8s 事件保留时长 — 取决于 etcd 事件 TTL（默认 1h），不可回溯历史事件

**POC 结论（2026-06-06）**：

| 验证项 | 结果 | 阻塞因素 | 所需权限 |
|--------|:----:|---------|---------|
| kubeconfig 获取 | ✅ 可行 | 无 | 无需额外权限（`cs:Get` 已有） |
| API Server 网络连通 | ✅ 可达 | 无 | 公网 SLB 已开放 |
| kubectl get 命令执行 | ❌ 被拒 | RBAC 未授权 | 需要在集群中创建 RoleBinding 或 ClusterRoleBinding |
| CloudAssistant RunCommand | ❌ 被拒 | RAM 无权限 | `ecs:RunCommand` |

**两个前置条件**才能完整解锁此能力：
1. **RAM 层面**：授权 `ecs:RunCommand` 或直接使用本地 kubectl（推荐）
2. **K8s RBAC 层面**：为当前 RAM 用户（UID: 208985268734007001

）绑定只读 ClusterRole（如 `view`）

**建议后续路径**：使用本地 kubectl 方式（不依赖 CloudAssistant），需要先完成 K8s RBAC 授权。

  ⚠️ 此任务为技术验证（POC），暂不纳入正式巡检流程

### 阈值定义

| 等级 | CPU Limits / capacity | Memory Limits / capacity | 含义 |
| 条件 | 说明 |
|:----:|------|
| 🟢 PASS | < 80% | 有充足余量 |
| 🟡 WARN | 80% ~ 120% | 正常超分范围，需关注 |
| 🔴 CRITICAL | 120% ~ 200% | 显著超分，高负载有风险 |
| 🔴🔴 CRITICAL+ | > 200% | 极端超分，必须治理 |

### 集成测试验证结果（2026-06-06）

```
✅ TC-01: 回溯模式一（days=7）通过
✅ TC-02: 回溯模式一（days=30）通过
✅ TC-03: 回溯模式二（指定时段）通过
✅ TC-04: 空输入容错通过
✅ TC-05: 回溯报告格式化通过
✅ TC-06: SLS 嗅探（空集群容错）通过
```

### 推理规则（新增至 inference-rules.md）

#### ACK-LIMITS-01: CPU Limits 超分 + 实际 usage 低

| 属性 | 内容 |
|------|------|
| **现象** | node.cpu.limit / node.cpu.capacity > 120% AND node.cpu.usage_rate / node.cpu.capacity < 60% |
| **推理** | 超分但实际负载不高、主要是 Pod request/limit 设置虚高 |
| **级别** | 🟡 Warning |
| **建议** | 降低虚高 Pod 的 limit/request（给出 Top 5 列表和推荐值） |

#### ACK-LIMITS-02: CPU Limits 超分 + usage 高

| 属性 | 内容 |
|------|------|
| **现象** | node.cpu.limit / node.cpu.capacity > 120% AND node.cpu.usage_rate / node.cpu.capacity > 70% |
| **推理** | 超分且实际负载高，流量高峰必然触发 CPU Throttling |
| **级别** | 🔴 Critical |
| **建议** | 扩容节点或迁移 Pod，同时优化高 limit Pod |

#### ACK-LIMITS-03: Memory Limits 超分

| 属性 | 内容 |
|------|------|
| **现象** | node.memory.limit / node.memory.capacity > 120% |
| **推理** | 内存超分，OOM 风险高 |
| **级别** | 🟡 Warning（>120%）/ 🔴 Critical（>180%） |
| **建议** | 查 OOMKilled Pod 数，查内存实际 usage，降虚高 limit |

### 质量门

| 编号 | 检查项 | 方法 | 通过标准 |
|------|--------|------|---------|
| Q5.1 | 节点级指标可查 | `aliyun cms DescribeMetricList --Namespace acs_k8s --MetricName node.cpu.limit` | 返回有效数据 |
| Q5.2 | 超卖比计算正确 | 手动算 capacity vs limit 的比值 | 与脚本输出一致 |
| Q5.3 | Pod 钻取有效 | 超分节点能定位到 Top 5 Pod | Pod 名、limit、usage 三元组完整 |
| Q5.4 | 阈值触发正确 | 注入 200% 超分节点 | 标记 Critical |
| Q5.5 | 报告可读 | 巡检报告中超分信息结构清晰 | Markdown 表格 + 建议可执行 |
| Q5.6 | Ruff Lint 零错误 | `ruff check scripts/*.py` | 0 error |
| Q5.7 | 推理规则联动 | 超分结果触发相应推理规则 | 修复建议链完整 |
| **Q5.8** | **回溯模式一（N天）** | `python3 -c "from _shared import backtrack_cms; r=backtrack_cms('cn-hangzhou','test-cid',['node1'],days=7); print(r['window'])"` | 输出包含 "过去 7 天" |
| **Q5.9** | **回溯模式二（指定时段）** | `python3 -c "from _shared import backtrack_cms; r=backtrack_cms('cn-hangzhou','test-cid',['node1'],start_time='2026-05-01T00:00:00Z',end_time='2026-05-07T23:59:59Z'); print(r['window'])"` | 输出包含 "2026-05-01 ~ 2026-05-07" |
| **Q5.10** | **SLS 嗅探** | `python3 -c "from _shared import check_audit_log_enabled; r=check_audit_log_enabled('cn-hangzhou','c3516669...'); print(f'audit={r[\"audit_enabled\"]}')"` | 返回布尔值，不抛异常 |
| **Q5.11** | **回溯报告格式化** | `python3 -c "from _shared import format_backtrack_report; r={'oversale_trend':[{'node':'n1','metric':'CPU超卖率','trend':[50,60,70],'message':'上升'}],'spikes':[],'restart_candidates':[],'oom_risk':[]}; print(format_backtrack_report(r))"` | 输出合法 Markdown，含表格 |

### 集成测试用例

#### TC-01: `backtrack_cms` 模式一 — 回溯最近 N 天

```python
# 用例：默认 7 天
from _shared import backtrack_cms
r = backtrack_cms("cn-hangzhou", "c35166695291649498d2d18153b3cbba0", [], days=7)
assert r["days"] == 7
assert "过去 7 天" in r["window"]

# 用例：回溯 30 天
r = backtrack_cms("cn-hangzhou", "c35166695291649498d2d18153b3cbba0", [], days=30)
assert r["days"] == 30
assert "过去 30 天" in r["window"]
```

#### TC-02: `backtrack_cms` 模式二 — 指定时段

```python
from _shared import backtrack_cms
r = backtrack_cms("cn-hangzhou", "c35166695291649498d2d18153b3cbba0", [],
                  start_time="2026-05-01T00:00:00Z",
                  end_time="2026-05-07T23:59:59Z")
assert r["days"] == 7  # days 参数保留，但不用于计算窗口
assert "2026-05-01" in r["window"]
assert "2026-05-07" in r["window"]
assert "~" in r["window"]
```

#### TC-03: `backtrack_cms` 无节点/无集群 — 空输入

```python
from _shared import backtrack_cms
r = backtrack_cms("cn-hangzhou", "", [])
assert r["oversale_trend"] == []
assert r["spikes"] == []
```

#### TC-04: `check_audit_log_enabled` 运行时嗅探

```python
from _shared import check_audit_log_enabled
r = check_audit_log_enabled("cn-hangzhou", "c35166695291649498d2d18153b3cbba0")
assert "audit_enabled" in r      # 一定返回这个字段
assert isinstance(r["audit_enabled"], bool)  # 布尔值不抛异常
# audit_enabled 当前为 false，但测试只验证接口可用性
```

#### TC-05: `format_backtrack_report` 输出格式

```python
from _shared import format_backtrack_report
r = format_backtrack_report({
    "oversale_trend": [
        {"node": "node-1", "metric": "CPU超卖率", "trend": [50, 62, 75], "message": "上升"}
    ],
    "spikes": [
        {"node": "node-1", "metric": "CPU超卖率", "time": "2026-06-01T14:00:00Z", "value": 95, "z": 3.2}
    ],
    "restart_candidates": [],
    "oom_risk": [],
})
assert "## 🔙" in r          # 含回溯章节标题
assert "趋势异常" in r        # 含趋势小节
assert "CPU超卖率" in r       # 含具体指标名
assert "突变事件" in r        # 含突变小节
```

#### TC-06: 完整集成场景 — 用户自然语言映射

| 用户表述 | Agent 解析 | 调用方式 | 验证点 |
|---------|-----------|---------|-------|
| "查一下过去一周集群状态" | `days=7` | `backtrack_cms(region, cid, nodes, days=7)` | window 含 "过去 7 天" |
| "最近三天节点有没有异常" | `days=3` | `backtrack_cms(region, cid, nodes, days=3)` | window 含 "过去 3 天" |
| "看下上个月的 oversale 趋势" | `days=30` | `backtrack_cms(region, cid, nodes, days=30)` | window 含 "过去 30 天" |
| "5月20号凌晨那次故障" | `start="2026-05-20T00:00:00Z", end="2026-05-21T00:00:00Z"` | `backtrack_cms(..., start_time=..., end_time=...)` | window 含 "2026-05-20 ~ 2026-05-21" |
| "今年元旦那周集群怎么样" | `start="2026-01-01T00:00:00Z", end="2026-01-07T23:59:59Z"` | `backtrack_cms(..., start_time=..., end_time=...)` | window 含 "2026-01-01 ~ 2026-01-07" |