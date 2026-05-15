# ACK Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for ACK (Container Service for Kubernetes). Each pattern follows the standardized schema.

## ACK-001 — Node NotReady 风暴

| 属性 | 内容 |
|------|------|
| 触发指标 | `NodeStatus` NotReady 比例 > 30% |
| 触发阈值 | NotReady 节点 > 30% 持续 5 min |
| 典型特征 | Pod 大量 Pending/Evicted，服务中断 |
| 关联指标 | `CpuUsage` + `MemoryUsage` 飙升（剩余节点过载） |
| 根因 | 1. 底层 ECS 故障 2. Kubelet 异常崩溃 3. 网络分区 |
| 诊断步骤 | 1. `kubectl describe node` 2. 查 ECS 状态 3. 查 kubelet 日志 |
| 修复方案 | 1. 重启 kubelet 2. 替换故障节点 3. 驱逐 Pod 到新节点 |
| 预防措施 | 节点 20% 告警、多可用区部署 |

## ACK-002 — Pod CrashLoopBackOff

| 属性 | 内容 |
|------|------|
| 触发指标 | `PodStatus` CrashLoopBackOff > 5 pods |
| 触发阈值 | CrashLoopBackOff > 5 pods 持续 3 min |
| 典型特征 | Pod 反复重启，事件中有 Back-off restarting failed container |
| 关联指标 | `CpuUsage` 可能正常，`MemoryUsage` 正常 |
| 根因 | 1. 应用代码异常 2. 容器启动命令错误 3. 依赖服务不可用 |
| 诊断步骤 | 1. `kubectl logs` 2. `kubectl describe pod` 3. 查应用日志 |
| 修复方案 | 1. 修复应用代码 2. 修正启动命令 3. 确认依赖服务 |
| 预防措施 | 就绪/存活探针配置、镜像版本管理 |

## ACK-003 — 集群资源耗尽

| 属性 | 内容 |
|------|------|
| 触发指标 | `CpuUsage` > 90% AND `MemoryUsage` > 90% |
| 触发阈值 | CPU + 内存双高持续 10 min |
| 典型特征 | 新 Pod 无法调度，Pending 状态堆积 |
| 关联指标 | `PodStatus` Pending 增加，磁盘使用率可能上升 |
| 根因 | 1. 流量突增导致 Pod 扩容 2. 无资源限制 3. 垃圾收集失败 |
| 诊断步骤 | 1. `kubectl top nodes` 2. `kubectl get pod -A` 3. 查调度事件 |
| 修复方案 | 1. 临时：删除非关键 Pod 2. 扩容 Node Pool |
| 预防措施 | 设置资源 Request/Limit、HPA 配置上限、节点池自动扩缩容 |

## ACK-004 — 镜像拉取失败

| 属性 | 内容 |
|------|------|
| 触发指标 | Pod Event 中有 Failed to pull image / ErrImagePull |
| 触发阈值 | 同 deployment 下 PullImage 失败 > 5 min |
| 典型特征 | Pod 状态为 ImagePullBackOff |
| 关联指标 | 网络指标可能正常，CPU/Memory 正常 |
| 根因 | 1. 镜像仓库认证失效 2. 镜像不存在 3. 网络不通 |
| 诊断步骤 | 1. `kubectl describe pod` 2. 检查 imagePullSecret 3. 手动 pull 测试 |
| 修复方案 | 1. 重新配置 imagePullSecret 2. 修正镜像标签 |
| 预防措施 | 镜像仓库 Token 自动轮换、镜像存在性校验 |

## ACK-005 — 网络插件 (CNI) 异常

| 属性 | 内容 |
|------|------|
| 触发指标 | Pod 网络不通 + Node NetworkInRate 异常 |
| 触发阈值 | 多个 Pod 同时网络不通，影响 > 50% 服务 |
| 典型特征 | DNS 解析失败、跨 Pod 通信中断 |
| 关联指标 | `NetworkInRate` / `NetworkOutRate` 突降 |
| 根因 | 1. Terway/Flannel Pod 异常 2. VPC ENI 耗尽 3. iptables 规则冲突 |
| 诊断步骤 | 1. `kubectl get pod -n kube-system \| grep cni` 2. 查 VPC ENI 配额 |
| 修复方案 | 1. 重启 CNI Pod 2. 扩容 ENI 配额 3. 升级 CNI 版本 |
| 预防措施 | CNI Pod 监控、ENI 配额预扩容、CNI 版本定期升级 |

## Cross-Product — ACK → ECS → RDS 级联故障

**场景：** ACK 节点过载 → Pod 调度失败 → RDS 连接数暴涨（重试风暴）

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | ACK 节点 CPU 100%，Pod Evicted | `alicloud-ack-ops` |
| T1 | +30s | Pod 在新节点启动，大量连接 RDS | `alicloud-rds-ops` |
| T2 | +2 min | RDS 连接数暴涨，慢查询增加 | `alicloud-rds-ops` |
| T3 | +5 min | SLB 5xx 上升，用户感知不可用 | `alicloud-slb-ops` |

**诊断顺序：** SLB 5xx → RDS 连接暴涨 → ACK Pod 重启 → ACK 节点过载 → 扩容 Node Pool

## Cross-Product — ACK → VPC 网络级联故障

**场景：** VPC ENI 配额耗尽 → ACK CNI 无法分配 IP → Pod Pending

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | VPC ENI 配额耗尽 | `alicloud-vpc-ops` |
| T1 | +1 min | CNI 插件无法分配 ENI | `alicloud-ack-ops` |
| T2 | +5 min | Pod Pending，HPA 无法扩容 | `alicloud-ack-ops` |

**诊断顺序：** Pod Pending → CNI 日志中 ENI 分配失败 → 查 VPC ENI 配额 → 扩容