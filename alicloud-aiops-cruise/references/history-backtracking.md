# 历史事件回溯方案 — History Backtracking

> **用途**：补足巡检"时间点快照"的局限性，提供向前回溯 N 天的事件检测能力。
> 解决"巡检这一刻没问题，但过去几天发生过什么"的问题。

---

## 背景：为什么需要回溯

当前 AIOps Cruise 的 4 个脚本（daily-health-check / emergency-troubleshoot / capacity-planning / pre-launch-check）都是**时间点快照**式的巡检——采集此刻的状态，出此刻的报告。

但在真实运维中，经常遇到这样的场景：

| 场景 | 问题 |
|------|------|
| "昨晚业务报警说慢，但现在查一切正常" | 无法回溯昨晚发生了什么 |
| "节点内存到底什么时候开始飙高的？" | 当前快照看不到趋势拐点 |
| "Pod 是不是重启过？" | 当前状态是 Running，看不出历史 |
| "这个节点 Oversale 是突然变高还是积累的？" | 需要趋势判断 |

**三层回溯体系**就是为这些场景设计的。

---

## 三层回溯架构

```
巡检时间点 T
     │
     ├── Layer 1: CMS 指标回溯 <- 0 额外成本
     │   ├── 数据源: acs_k8s (保留 30 天)
     │   ├── 回溯窗口: 7 天 / 30 天
     │   └── 能力: 趋势分析、突变检测、基线偏离
     │
     ├── Layer 2: SLS 审计日志回溯 <- 需开启审计日志
     │   ├── 数据源: SLS (kube-apiserver 审计日志)
     │   ├── 回溯窗口: 自定义
     │   └── 能力: 精确 K8s 事件定位
     │
     └── Layer 3: CloudAssistant + kubectl <- 当前快照
         ├── 数据源: kubectl get events (ECS 内执行)
         ├── 回溯窗口: ~1 小时 (K8s 默认事件保留)
         └── 能力: 当前异常事件快照
```

---

## Layer 1: CMS 指标回溯（核心方案，零额外成本）

### 原理

阿里云 CMS（CloudMonitor）的 `acs_k8s` 命名空间指标默认保留 **30 天** 以上的历史数据。我们可以通过 `DescribeMetricList` 查询任意时间范围的时序数据，做趋势分析和异常检测。

### 可回溯的指标

| 指标 | 回溯用途 | 检测模式 |
|------|---------|---------|
| `node.cpu.limit` | 节点 CPU limits 超分比趋势 | 连续上升 -> 需要治理 |
| `node.cpu.usage_rate` | 节点实际 CPU 使用趋势 | 突增 -> 可能有流量尖峰 |
| `node.memory.limit` | 节点内存 limits 超分比趋势 | 连续上升 -> 需要治理 |
| `node.memory.working_set` | 节点实际内存使用趋势 | 突增接近 capacity -> OOM 风险 |
| `node.cpu.oversale_rate` | CPU 超卖率趋势 | 持续 > 80% 且上升 -> 风险 |
| `node.memory.oversale_rate` | 内存超卖率趋势 | 持续 > 80% 且上升 -> 风险 |
| `pod.cpu.usage_rate` | 逐个 Pod CPU 使用趋势 | 归零 -> 可能刚重启过 |
| `pod.memory.working_set` | 逐个 Pod 内存使用趋势 | 突降归零 -> 可能 OOMKill 后重启 |
| `pod.memory.utilization` | Pod 内存利用率 (working_set/limit) | 接近 100% -> 高 OOM 风险 |
| `cluster.cpu.utilization` | 集群级 CPU 水位趋势 | 整体健康度 |
| `cluster.memory.utilization` | 集群级内存水位趋势 | 整体健康度 |

### 回溯分析算法

```python
# 伪代码：7 天回溯分析
def backtrack_7d(cluster_id, region):
    now = datetime.now(UTC)
    d7 = now - timedelta(days=7)
    
    report = {
        "oversale_trend": {},      # 节点超卖率趋势
        "oom_risk_pods": [],       # 高 OOM 风险的 Pod
        "restart_candidates": [],  # 疑似重启的 Pod
        "resource_spikes": [],     # 资源使用突增事件
    }
    
    # 1. 节点级趋势
    for node in get_nodes(cluster_id):
        cpu_oversale = query_cms("node.cpu.oversale_rate", node, d7, now)
        mem_oversale = query_cms("node.memory.oversale_rate", node, d7, now)
        
        # 检测连续上升趋势
        if is_continuous_rising(cpu_oversale):
            report["oversale_trend"][node] = "CPU 超卖率连续上升"
        
        # 检测突变
        spikes = detect_spikes(mem_oversale)
        if spikes:
            report["resource_spikes"].append({"node": node, "spikes": spikes})
    
    # 2. Pod 级事件推断
    for pod in get_pods(cluster_id):
        mem_ws = query_cms("pod.memory.working_set", pod, d7, now)
        mem_util = query_cms("pod.memory.utilization", pod, d7, now)
        
        # 检测疑似 OOMKill: working_set 突降至 0
        if has_sudden_drop_to_zero(mem_ws):
            report["restart_candidates"].append({
                "pod": pod,
                "reason": "疑似 OOMKill 重启",
                "time": find_drop_time(mem_ws)
            })
        
        # 检测高 OOM 风险
        if max(mem_util) > 0.95:
            report["oom_risk_pods"].append({
                "pod": pod,
                "max_util": f"{max(mem_util)*100:.1f}%"
            })
    
    return report
```

### 输出示例（巡检报告中的回溯章节）

```
## [BACK] 历史回溯（过去 7 天）

### 节点趋势异常
- node-i-xxxx: CPU 超卖率连续 5 天上升 (65%->82%->88%->91%->95%) CRITICAL
- node-i-yyyy: 内存 usage 在 06-03 14:00 出现尖峰 (12G->23G) WARNING

### Pod 疑似重启
- default/order-svc-xxx: 06-02 03:15 working_set 突降至 0 (疑似 OOMKill) CRITICAL
- kube-system/coredns-xxx: 06-01 22:30 重启 (正常波动) SAFE

### OOM 高风险 Pod
- default/payment-svc (memory.utilization=97.3%) CRITICAL
- default/user-svc (memory.utilization=91.8%) WARNING
```

---

## Layer 2: SLS 审计日志回溯（需开启审计日志）

### 检查方式

```bash
# 检查审计日志是否开启
aliyun cs GET /clusters/{clusterId}/audit

# 返回示例（未开启）
{
    "audit_enabled": false,
    "sls_project_name": ""
}

# 检查控制面日志是否开启
aliyun cs GET /clusters/{clusterId}/controlplanelog

# 返回示例（未开启）
{
    "components": null
}
```

### 当前环境状态

> **当前环境 `海鼎-测试集群  (c3516669...)` 检查结果（2026-06-06）：**
> - `audit_enabled: false` — FAIL 审计日志未开启
> - `components: null` — FAIL 控制面日志未开启
>
> **结论**：SLS 审计回溯路径不可用，降级到 Layer 1 + Layer 3。

### 如果开启，能查到什么

| SLS 日志类型 | 包含内容 | 可回溯的 K8s 事件 |
|-------------|---------|------------------|
| kube-apiserver 审计日志 | ALL K8s API 调用 | Pod 创建/删除/驱逐、Node 状态变更、事件写入 |
| kube-scheduler 日志 | 调度决策 | Pod 调度失败、资源不足 |
| kube-controller-manager 日志 | 控制器操作 | ReplicaSet 扩缩、Node 控制器动作 |
| kubelet 日志 | 节点级操作 | OOMKill、容器重启、磁盘压力 |

### 开启方式（如需）

```bash
# 开启审计日志（需要 SLR 权限）
aliyun cs PUT /clusters/{clusterId}/audit_log \
  --body '{"audit_log_enable":true}'

# 开启控制面日志
aliyun cs PUT /clusters/{ClusterId}/controlplanelog \
  --body '{"components":["apiserver","scheduler","controller-manager"]}'
```

---

## Layer 3: CloudAssistant + kubectl events（当前快照）

### 原理

通过 CloudAssistant 在任意 ECS 节点上执行 `kubectl` 命令，获取当前集群的 K8s 事件。

### 命令

```bash
# 获取所有 namespace 的事件，按时间倒排
aliyun ecs RunCommand \
  --CommandContent "kubectl get events --all-namespaces --sort-by='.lastTimestamp' --output=wide" \
  --InstanceId i-xxx \
  --RegionId cn-hangzhou
```

### 能获取到的事件类型

| 事件类型 | 原因 | 含义 |
|---------|------|------|
| `Pod` | `OOMKill` | 容器内存超限被 Kill |
| `Pod` | `CrashLoopBackOff` | Pod 反复崩溃重启 |
| `Pod` | `BackOff` | Pod 启动失败 |
| `Node` | `NodeNotReady` | 节点失联 |
| `Node` | `Rebooted` | 节点重启 |
| `Pod` | `FailedScheduling` | Pod 调度失败（资源不足） |
| `Pod` | `Evicted` | Pod 被驱逐 |
| `Pod` | `Unhealthy` | 健康检查失败 |

### 局限性

- **K8s 事件默认只保留 ~1 小时**（由 `--event-ttl` 控制）
- 只能看到**当前时刻**附近的异常，无法回溯历史
- 需要 ECS 实例安装有 `kubectl` 且配置了 kubeconfig

---

## 综合回溯策略总表

| 维度 | Layer 1 (CMS) | Layer 2 (SLS) | Layer 3 (kubectl) |
|------|:------------:|:-------------:|:-----------------:|
| **是否需要额外配置** | FAIL 不需要 | PASS 需开启审计日志 | PASS 需安装 kubectl |
| **当前环境可用?** | PASS **可用** | FAIL 未开启 | [WARN] 需检查 |
| **回溯窗口** | 7~30 天 | 自定义 | ~1 小时 |
| **精确度** | 推断级（趋势） | 精确级（事件） | 精确级（事件） |
| **覆盖范围** | 资源水位 + 趋势 | ALL K8s API 操作 | 当前异常事件 |
| **巡检集成难度** | 低（已有 CMS 查询能力） | 中（需 SLS SDK） | 中（需 CloudAssistant） |

### 推荐实施路径

```
Phase 1 (P0): Layer 1 CMS 回溯
  -> 在 daily-health-check 中集成 7 天回溯分析
  -> 检测趋势异常 + 疑似事件推断
  -> 输出到巡检报告的「历史回溯」章节

Phase 2 (P1): Layer 3 kubectl 兜底
  -> pre-flight 检查 kubectl 是否可用
  -> 在 emergency-troubleshoot 中获取当前事件
  -> 辅助故障定位

Phase 3 (P2): Layer 2 SLS 增强
  -> 如果用户开启了审计日志，自动接入
  -> 精确事件回溯
```

---

## TODO 集成

- [ ] **Sprint 5.8** CMS 7天回溯检测函数 (`_shared.py` 新增 `backtrack_7d()`)
- [ ] **Sprint 5.9** daily-health-check 增加「历史回溯」报告章节
- [ ] **Sprint 5.10** emergency-troubleshoot 集成 Layer 3 kubectl events
- [ ] 更新 `threshold-definitions.md` 增加回溯检测阈值
- [ ] 更新 `inference-rules.md` 增加回溯推理规则