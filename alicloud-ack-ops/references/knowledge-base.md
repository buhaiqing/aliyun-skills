# ACK Fault Pattern Knowledge Base

> **Purpose:** Fault pattern library for ACK (Container Service for Kubernetes). Each pattern follows the standardized schema.
> **Coverage:** 20+ patterns covering Cluster, Node, Pod, Service, Ingress, Storage, Network, Security, Addon failures.

---

## 集群与节点故障模式 (Cluster & Node)

### ACK-001 — Node NotReady 风暴

| 属性 | 内容 |
|------|------|
| 触发指标 | `NodeStatus` NotReady 比例 > 30% |
| 触发阈值 | NotReady 节点 > 30% 持续 5 min |
| 典型特征 | Pod 大量 Pending/Evicted，服务中断 |
| 关联指标 | `CpuUsage` + `MemoryUsage` 飙升（剩余节点过载） |
| 根因 | 1. 底层 ECS 故障 2. Kubelet 异常崩溃 3. 网络分区 4. 证书过期 |
| 诊断步骤 | 1. `kubectl describe node` 2. 查 ECS 状态 3. 查 kubelet 日志 4. 检查证书有效期 |
| 修复方案 | 1. 重启 kubelet 2. 替换故障节点 3. 驱逐 Pod 到新节点 4. 更新集群证书 |
| 预防措施 | 节点 20% 告警、多可用区部署、证书自动轮换 |
| 严重等级 | P0-Critical |
| 影响范围 | 集群级 |

### ACK-002 — 集群资源耗尽

| 属性 | 内容 |
|------|------|
| 触发指标 | `CpuUsage` > 90% AND `MemoryUsage` > 90% |
| 触发阈值 | CPU + 内存双高持续 10 min |
| 典型特征 | 新 Pod 无法调度，Pending 状态堆积 |
| 关联指标 | `PodStatus` Pending 增加，磁盘使用率可能上升 |
| 根因 | 1. 流量突增导致 Pod 扩容 2. 无资源限制 3. 垃圾收集失败 4. Node Pool 配额不足 |
| 诊断步骤 | 1. `kubectl top nodes` 2. `kubectl get pod -A` 3. 查调度事件 4. 查 Node Pool 配额 |
| 修复方案 | 1. 临时：删除非关键 Pod 2. 扩容 Node Pool 3. 调整资源 Request/Limit |
| 预防措施 | 设置资源 Request/Limit、HPA 配置上限、节点池自动扩缩容、资源预留 20% |
| 严重等级 | P1-High |
| 影响范围 | 集群级 |

### ACK-003 — 集群升级失败

| 属性 | 内容 |
|------|------|
| 触发指标 | 集群状态 `upgrading` 超过 60 分钟 |
| 触发阈值 | 升级任务超时或失败状态 |
| 典型特征 | 集群 API Server 不稳定，部分节点版本不一致 |
| 关联指标 | Node K8s 版本不一致，Addon 状态异常 |
| 根因 | 1. 自定义组件不兼容新版本 2. 节点升级超时 3. Addon 依赖冲突 |
| 诊断步骤 | 1. 查集群升级日志 2. 检查组件兼容性列表 3. 验证节点升级状态 |
| 修复方案 | 1. 回滚到旧版本 2. 先升级兼容组件 3. 分批次升级节点 |
| 预防措施 | 升级前检查兼容性、先在测试环境验证、制定回滚计划 |
| 严重等级 | P1-High |
| 影响范围 | 集群级 |

### ACK-004 — Node Pool 扩容失败

| 属性 | 内容 |
|------|------|
| 触发指标 | Node Pool `desired_size` != `current_size` 超过 15 分钟 |
| 触发阈值 | 扩容任务卡住或失败 |
| 典型特征 | 新节点未加入集群，节点池状态异常 |
| 关联指标 | ECS 实例创建状态、VSwitch 配额 |
| 根因 | 1. ECS 配额不足 2. VSwitch IP 耗尽 3. 实例规格缺货 4. RAM 权限不足 |
| 诊断步骤 | 1. 查 Node Pool 详情 2. 检查 ECS 配额 3. 验证 VSwitch IP 数量 4. 检查 RAM 权限 |
| 修复方案 | 1. 申请配额提升 2. 添加新 VSwitch 3. 切换实例规格 4. 修复 RAM 权限 |
| 预防措施 | 预估配额需求、多 VSwitch 分布、配额告警 |
| 严重等级 | P2-Medium |
| 影响范围 | Node Pool 级 |

---

## Pod 故障模式 (Pod)

### ACK-005 — Pod CrashLoopBackOff 批量爆发

| 属性 | 内容 |
|------|------|
| 触发指标 | `PodStatus` CrashLoopBackOff > 5 pods |
| 触发阈值 | CrashLoopBackOff > 5 pods 持续 3 min |
| 典型特征 | Pod 反复重启，事件中有 Back-off restarting failed container |
| 关联指标 | `CpuUsage` 可能正常，`MemoryUsage` 正常 |
| 根因 | 1. 应用代码异常 2. 容器启动命令错误 3. 依赖服务不可用 4. 配置错误 |
| 诊断步骤 | 1. `kubectl logs` 2. `kubectl describe pod` 3. 查应用日志 4. 检查配置文件 |
| 修复方案 | 1. 修复应用代码 2. 修正启动命令 3. 确认依赖服务 4. 修正配置 |
| 预防措施 | 就绪/存活探针配置、镜像版本管理、配置校验 |
| 严重等级 | P1-High |
| 影响范围 | Namespace 级 |

### ACK-006 — Pod Pending 资源不足

| 属性 | 内容 |
|------|------|
| 触发指标 | `PodStatus` Pending 持续 > 10 min |
| 触发阈值 | Pending Pod 无法调度超过阈值时间 |
| 典型特征 | 事件中有 Insufficient cpu/memory/node |
| 关联指标 | Node CPU/Memory 使用率、Pod 资源请求 |
| 根因 | 1. 资源 Request 过大 2. Node Pool 容量不足 3. 节点选择器限制 4. 污点/容忍配置错误 |
| 诊断步骤 | 1. `kubectl describe pod` 2. `kubectl top nodes` 3. 检查 Pod 资源请求 4. 查节点选择器 |
| 修复方案 | 1. 降低资源 Request 2. 扩容 Node Pool 3. 调整节点选择器 4. 添加容忍配置 |
| 预防措施 | 合理设置 Request/Limit、配置自动扩容、预留资源缓冲 |
| 严重等级 | P2-Medium |
| 影响范围 | Pod 级 |

### ACK-007 — Pod 频繁驱逐 (Evicted)

| 属性 | 内容 |
|------|------|
| 触发指标 | `PodStatus` Evicted 频率 > 10/hour |
| 触发阈值 | 节点压力导致 Pod 频繁被驱逐 |
| 典型特征 | 事件中有 The node was low on resource |
| 关联指标 | Node DiskPressure/MemoryPressure/PIDPressure |
| 根因 | 1. 节点磁盘满 2. 节点内存不足 3. 进程数过多 4. 资源预留不足 |
| 诊断步骤 | 1. `kubectl describe node` 2. 查节点压力条件 3. 检查系统资源使用 |
| 修复方案 | 1. 清理节点磁盘 2. 扩容节点 3. 调整 Pod 资源限制 4. 增加驱逐阈值 |
| 预防措施 | 节点资源预留、磁盘自动清理、PDB 配置 |
| 严重等级 | P2-Medium |
| 影响范围 | Namespace 级 |

### ACK-008 — 镜像拉取失败

| 属性 | 内容 |
|------|------|
| 触发指标 | Pod Event 中有 Failed to pull image / ErrImagePull |
| 触发阈值 | 同 deployment 下 PullImage 失败 > 5 min |
| 典型特征 | Pod 状态为 ImagePullBackOff |
| 关联指标 | 网络指标可能正常，CPU/Memory 正常 |
| 根因 | 1. 镜像仓库认证失效 2. 镜像不存在 3. 网络不通 4. 镜像太大拉取超时 |
| 诊断步骤 | 1. `kubectl describe pod` 2. 检查 imagePullSecret 3. 手动 pull 测试 4. 检查镜像大小 |
| 修复方案 | 1. 重新配置 imagePullSecret 2. 修正镜像标签 3. 配置镜像加速 4. 预拉取镜像 |
| 预防措施 | 镜像仓库 Token 自动轮换、镜像存在性校验、镜像加速配置 |
| 严重等级 | P2-Medium |
| 影响范围 | Pod 级 |

### ACK-009 — OOMKilled 内存溢出

| 属性 | 内容 |
|------|------|
| 触发指标 | Pod 状态 OOMKilled |
| 触发阈值 | 容器因内存超限被杀死 |
| 典型特征 | 事件中有 OOMKilled，Exit Code 137 |
| 关联指标 | 容器内存使用趋势 |
| 根因 | 1. 内存 Limit 设置过低 2. 应用内存泄漏 3. 数据处理负载过大 |
| 诊断步骤 | 1. `kubectl describe pod` 2. 查容器内存使用历史 3. 分析内存泄漏 |
| 修复方案 | 1. 增加内存 Limit 2. 修复内存泄漏 3. 优化数据处理逻辑 |
| 预防措施 | 合理设置内存 Limit、内存监控告警、定期内存分析 |
| 严重等级 | P2-Medium |
| 影响范围 | Pod 级 |

---

## 网络与服务故障模式 (Network & Service)

### ACK-010 — CNI 网络插件异常

| 属性 | 内容 |
|------|------|
| 触发指标 | Pod 网络不通 + Node NetworkInRate 异常 |
| 触发阈值 | 多个 Pod 同时网络不通，影响 > 50% 服务 |
| 典型特征 | DNS 解析失败、跨 Pod 通信中断 |
| 关联指标 | `NetworkInRate` / `NetworkOutRate` 突降 |
| 根因 | 1. Terway/Flannel Pod 异常 2. VPC ENI 耗尽 3. iptables 规则冲突 4. CNI 配置错误 |
| 诊断步骤 | 1. `kubectl get pod -n kube-system \| grep cni` 2. 查 VPC ENI 配额 3. 检查 iptables |
| 修复方案 | 1. 重启 CNI Pod 2. 扩容 ENI 配额 3. 升级 CNI 版本 4. 修正 CNI 配置 |
| 预防措施 | CNI Pod 监控、ENI 配额预扩容、CNI 版本定期升级 |
| 严重等级 | P0-Critical |
| 影响范围 | 集群级 |

### ACK-011 — DNS 解析失败

| 属性 | 内容 |
|------|------|
| 触发指标 | 应用 Pod DNS 解析超时或失败 |
| 触发阈值 | DNS 查询失败率 > 5% |
| 典型特征 | 应用日志有 DNS timeout、connection refused |
| 关联指标 | CoreDNS Pod 状态、CPU/Memory 使用 |
| 根因 | 1. CoreDNS Pod 异常 2. DNS 缓存配置问题 3. 上游 DNS 不通 4. Pod DNS 配置错误 |
| 诊断步骤 | 1. `kubectl get pod -n kube-system \| grep coredns` 2. 查 CoreDNS 日志 3. 测试上游 DNS |
| 修复方案 | 1. 重启 CoreDNS 2. 调整 DNS 缓存配置 3. 配置备用上游 DNS 4. 修正 Pod DNS 配置 |
| 预防措施 | CoreDNS 监控、DNS 缓存优化、多上游 DNS 配置 |
| 严重等级 | P1-High |
| 影动范围 | Namespace 级 |

### ACK-012 — Service Endpoints 空缺

| 属性 | 内容 |
|------|------|
| 触发指标 | Service Endpoints 为空或部分缺失 |
| 触发阈值 | Service 无后端 Pod 超过 5 min |
| 典型特征 | 应用访问 Service 返回连接拒绝 |
| 关联指标 | Pod 状态、Label 匹配情况 |
| 根因 | 1. Pod Label 与 Service Selector 不匹配 2. Pod 未 Ready 3. EndpointSlice 异常 |
| 诊断步骤 | 1. `kubectl get endpoints` 2. `kubectl describe service` 3. 检查 Pod Label |
| 修复方案 | 1. 修正 Service Selector 2. 等待 Pod Ready 3. 重启 EndpointSlice 控制器 |
| 预防措施 | Service Selector 校验、就绪探针配置 |
| 严重等级 | P2-Medium |
| 影动范围 | Service 级 |

### ACK-013 — Ingress 502/503 错误

| 属性 | 内容 |
|------|------|
| 触发指标 | Ingress 返回 502/503 状态码 |
| 触发阈值 | 5xx 错误率 > 1% 持续 5 min |
| 典型特征 | 用户访问应用失败，Nginx Ingress 日志有错误 |
| 关联指标 | Ingress Controller Pod 状态、后端 Pod 健康状态 |
| 根因 | 1. 后端 Pod 不健康 2. Service Endpoints 空 3. Ingress 配置错误 4. 负载过高 |
| 诊断步骤 | 1. 查 Ingress Controller 日志 2. `kubectl get ingress` 3. 检查后端 Pod 健康状态 |
| 修复方案 | 1. 修复后端 Pod 2. 确保 Service 有 Endpoints 3. 修正 Ingress 配置 4. 扩容 Ingress Controller |
| 预防措施 | Ingress 监控、后端健康检查、Ingress Controller 扩容配置 |
| 严重等级 | P1-High |
| 影动范围 | Ingress 级 |

---

## 存储故障模式 (Storage)

### ACK-014 — PVC Pending 无法绑定

| 属性 | 内容 |
|------|------|
| 触发指标 | PVC 状态 Pending 持续 > 10 min |
| 触发阈值 | PVC 无法自动绑定 PV |
| 典型特征 | 事件中有 no persistent volumes available、等待绑定 |
| 关联指标 | PV 状态、StorageClass 配置 |
| 根因 | 1. StorageClass 不存在 2. PV 容量不足 3. 可用区不匹配 4. 访问模式不兼容 |
| 诊断步骤 | 1. `kubectl describe pvc` 2. `kubectl get pv` 3. 检查 StorageClass 配置 |
| 修复方案 | 1. 创建/修复 StorageClass 2. 扩容云盘配额 3. 调整可用区配置 4. 修改访问模式 |
| 预防措施 | StorageClass 校验、云盘配额预估、多可用区 PV |
| 严重等级 | P2-Medium |
| 影动范围 | PVC 级 |

### ACK-015 — 云盘挂载失败

| 属性 | 内容 |
|------|------|
| 触发指标 | Pod 事件有 AttachVolume failed / MountVolume failed |
| 触发阈值 | 云盘挂载失败 > 5 min |
| 典型特征 | Pod 状态 ContainerCreating 卡住 |
| 关联指标 | PV 状态、云盘状态、CSI Pod 状态 |
| 根因 | 1. 云盘不存在 2. 云盘状态异常 3. CSI 驱动异常 4. 挂载点冲突 |
| 诊断步骤 | 1. `kubectl describe pod` 2. 查 CSI Pod 日志 3. 检查云盘状态 |
| 修复方案 | 1. 恢复云盘 2. 重启 CSI Pod 3. 清理挂载点 4. 替换 PV |
| 预防措施 | 云盘状态监控、CSI 驱动监控、挂载点管理 |
| 严重等级 | P2-Medium |
| 影动范围 | Pod 级 |

### ACK-016 — 存储扩容失败

| 属性 | 内容 |
|------|------|
| 触发指标 | PVC 扩容后状态异常或失败 |
| 触发阈值 | 云盘扩容操作失败或超时 |
| 典型特征 | PVC 容量未变化，事件中有 Resize failed |
| 关联指标 | 云盘容量、Pod 文件系统大小 |
| 根因 | 1. 云盘类型不支持在线扩容 2. ECS 实例状态异常 3. 文件系统扩容失败 |
| 诊断步骤 | 1. `kubectl describe pvc` 2. 查云盘扩容日志 3. 检查文件系统 |
| 修复方案 | 1. 使用支持扩容的云盘类型 2. 恢复 ECS 状态 3. 手动扩容文件系统 |
| 预防措施 | 选择 ESSD 云盘、配置自动扩容策略、文件系统监控 |
| 严重等级 | P2-Medium |
| 影动范围 | PVC 级 |

---

## 安全与权限故障模式 (Security)

### ACK-017 — RAM 权限不足

| 属性 | 内容 |
|------|------|
| 触发指标 | API 返回 ErrorCheckAcl / Forbidden 错误 |
| 触发阈值 | 集群操作因权限问题失败 |
| 典型特征 | 无法创建/修改资源，错误信息含权限相关 |
| 关联指标 | RAM 角色/策略配置 |
| 根因 | 1. RAM 角色未授权 2. RAM 策略缺少必要 Action 3. 跨账号权限问题 |
| 诊断步骤 | 1. 检查 RAM 角色授权 2. 查 RAM 策略内容 3. 验证账号权限 |
| 修复方案 | 1. 授权必要 RAM 角色 2. 添加缺失 Action 到策略 3. 配置跨账号授权 |
| 预防措施 | RAM 权限审计、权限变更审批流程 |
| 严重等级 | P1-High |
| 影动范围 | 集群级 |

### ACK-018 — 集群证书过期

| 属性 | 内容 |
|------|------|
| 触发指标 | API Server 连接失败，证书校验错误 |
| 触发阈值 | 集群证书即将过期或已过期 |
| 典型特征 | kubectl 连接失败，证书有效期警告 |
| 关联指标 | 证书创建时间、有效期 |
| 根因 | 1. 集群证书过期 2. 未配置自动轮换 3. 手动更新遗漏 |
| 诊断步骤 | 1. 检查证书有效期 2. `kubectl get csr` 3. 查集群证书状态 |
| 修复方案 | 1. 更新集群证书 2. 配置自动轮换 3. 分批更新节点证书 |
| 预防措施 | 证书过期告警（提前 30 天）、自动轮换配置 |
| 严重等级 | P0-Critical |
| 影动范围 | 集群级 |

### ACK-019 — RBAC 权限配置错误

| 属性 | 内容 |
|------|------|
| 触发指标 | ServiceAccount 无法访问资源 |
| 触发阈值 | kubectl 返回 Forbidden 错误 |
| 典型特征 | 应用 Pod 无法访问 API，权限拒绝 |
| 关联指标 | ClusterRole/RoleBinding 配置 |
| 根因 | 1. Role/ClusterRole 缺少必要权限 2. RoleBinding 未绑定 3. ServiceAccount 不存在 |
| 诊断步骤 | 1. `kubectl describe role` 2. `kubectl describe rolebinding` 3. 检查 ServiceAccount |
| 修复方案 | 1. 添加必要权限到 Role 2. 创建 RoleBinding 3. 创建 ServiceAccount |
| 预防措施 | RBAC 配置审计、最小权限原则 |
| 严重等级 | P2-Medium |
| 影动范围 | Namespace 级 |

---

## Addon 故障模式 (Addon)

### ACK-020 — Ingress Controller 异常

| 属性 | 内容 |
|------|------|
| 触发指标 | Ingress Controller Pod 状态异常 |
| 触发阈值 | Nginx Ingress Pod NotReady 或 CrashLoopBackOff |
| 典型特征 | 所有 Ingress 路由失效 |
| 关联指标 | Ingress Controller CPU/Memory、SLB 状态 |
| 根因 | 1. 配置错误 2. 资源不足 3. 版本不兼容 4. SLB 异常 |
| 诊断步骤 | 1. `kubectl get pod -n kube-system \| grep ingress` 2. 查 Ingress Controller 日志 3. 检查 SLB |
| 修复方案 | 1. 修正配置 2. 扩容资源 3. 升级版本 4. 恢复 SLB |
| 预防措施 | Ingress Controller 监控、配置校验、版本管理 |
| 严重等级 | P0-Critical |
| 影动范围 | 集群级 |

### ACK-021 — Metrics Server 异常

| 属性 | 内容 |
|------|------|
| 触发指标 | `kubectl top` 命令失败 |
| 触发阈值 | 无法获取 Pod/Node 资源指标 |
| 典型特征 | HPA 无法工作，资源监控不可用 |
| 关联指标 | Metrics Server Pod 状态 |
| 根因 | 1. Metrics Server Pod 异常 2. API Service 未注册 3. 资源不足 |
| 诊断步骤 | 1. `kubectl get pod -n kube-system \| grep metrics` 2. `kubectl get apiservice` 3. 检查 Pod 资源 |
| 修复方案 | 1. 重启 Metrics Server 2. 注册 API Service 3. 扩容资源 |
| 预防措施 | Metrics Server 监控、HPA 依赖检查 |
| 严重等级 | P2-Medium |
| 影动范围 | 集群级 |

### ACK-022 — CSI 驱动异常

| 属性 | 内容 |
|------|------|
| 触发指标 | 所有 Pod PVC 挂载失败 |
| 触发阈值 | CSI Controller/Node Plugin 异常 |
| 典型特征 | 新 Pod 无法启动，存储操作全部失败 |
| 关联指标 | CSI Pod 状态、云盘 API 响应 |
| 根因 | 1. CSI Pod CrashLoopBackOff 2. CSI 配置错误 3. 云盘 API 异常 |
| 诊断步骤 | 1. `kubectl get pod -n kube-system \| grep csi` 2. 查 CSI 日志 3. 检查云盘 API |
| 修复方案 | 1. 重启 CSI Pod 2. 修正 CSI 配置 3. 检查云盘服务状态 |
| 预防措施 | CSI 驱动监控、存储操作审计 |
| 严重等级 | P0-Critical |
| 影动范围 | 集群级 |

---

## 跨产品级联故障模式 (Cross-Product)

### ACK-X001 — ACK → ECS → RDS 级联故障

**场景：** ACK 节点过载 → Pod 调度失败 → RDS 连接数暴涨（重试风暴）

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | ACK 节点 CPU 100%，Pod Evicted | `alicloud-ack-ops` |
| T1 | +30s | Pod 在新节点启动，大量连接 RDS | `alicloud-rds-ops` |
| T2 | +2 min | RDS 连接数暴涨，慢查询增加 | `alicloud-rds-ops` |
| T3 | +5 min | SLB 5xx 上升，用户感知不可用 | `alicloud-slb-ops` |

**诊断顺序：** SLB 5xx → RDS 连接暴涨 → ACK Pod 重启 → ACK 节点过载 → 扩容 Node Pool

**修复方案：**
1. ACK：扩容 Node Pool，增加节点
2. RDS：临时增加连接数上限，清理异常连接
3. SLB：调整健康检查阈值
4. 应用：实现优雅重启，避免重试风暴

### ACK-X002 — ACK → VPC 网络级联故障

**场景：** VPC ENI 配额耗尽 → ACK CNI 无法分配 IP → Pod Pending

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | VPC ENI 配额耗尽 | `alicloud-vpc-ops` |
| T1 | +1 min | CNI 插件无法分配 ENI | `alicloud-ack-ops` |
| T2 | +5 min | Pod Pending，HPA 无法扩容 | `alicloud-ack-ops` |

**诊断顺序：** Pod Pending → CNI 日志中 ENI 分配失败 → 查 VPC ENI 配额 → 扩容 ENI 配额

**修复方案：**
1. VPC：申请 ENI 配额提升
2. ACK：添加新 VSwitch 扩展 IP 池
3. CNI：配置备用 IP 池

### ACK-X003 — ACK → SLB 级联故障

**场景：** SLB 后端服务器组异常 → Ingress 不可用 → 应用服务中断

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | SLB 后端健康检查失败 | `alicloud-slb-ops` |
| T1 | +1 min | Ingress Controller 无法转发流量 | `alicloud-ack-ops` |
| T2 | +3 min | 应用请求全部失败 | `alicloud-ack-ops` |

**诊断顺序：** 应用请求失败 → Ingress 日志 → SLB 后端状态 → 恢复 SLB 后端

**修复方案：**
1. SLB：恢复后端服务器健康
2. ACK：重启 Ingress Controller Pod
3. 应用：检查 Pod 健康状态

### ACK-X004 — ACK → OSS 存储级联故障

**场景：** OSS Bucket 配额或权限问题 → PV 挂载失败 → 应用无法启动

| 级联阶段 | 时间 | 现象 | Skill 负责 |
|----------|------|------|------------|
| T0 | 00:00 | OSS Bucket 访问异常 | `alicloud-oss-ops` |
| T1 | +1 min | CSI 驱动无法挂载 OSS | `alicloud-ack-ops` |
| T2 | +5 min | Pod ContainerCreating 卡住 | `alicloud-ack-ops` |

**诊断顺序：** Pod 挂载失败 → CSI 日志 → OSS Bucket 状态 → 恢复 OSS 访问

**修复方案：**
1. OSS：恢复 Bucket 访问权限或配额
2. ACK：重启 CSI Pod，清理挂载缓存
3. PV：验证 PV 配置正确

---

## 诊断脚本模板

### 快速诊断脚本 1: 节点健康检查

```bash
#!/bin/bash
# 节点健康快速诊断
echo "=== Node Health Check ==="
kubectl get nodes -o wide
kubectl describe nodes | grep -A5 "Conditions:"
kubectl top nodes
```

### 快速诊断脚本 2: Pod 异常排查

```bash
#!/bin/bash
# Pod 异常快速排查
echo "=== Pod Status Summary ==="
kubectl get pods -A --field-selector=status.phase!=Running | head -20
echo ""
echo "=== CrashLoopBackOff Pods ==="
kubectl get pods -A | grep CrashLoopBackOff
echo ""
echo "=== Pending Pods ==="
kubectl get pods -A | grep Pending | while read line; do
  POD=$(echo $line | awk '{print $2}')
  NS=$(echo $line | awk '{print $1}')
  echo "Describing $POD in $NS:"
  kubectl describe pod $POD -n $NS | grep -A10 "Events:"
done
```

### 快速诊断脚本 3: 网络连通性检查

```bash
#!/bin/bash
# 网络连通性快速检查
echo "=== CoreDNS Status ==="
kubectl get pods -n kube-system | grep coredns
kubectl logs -n kube-system -l k8s-app=coredns --tail=20
echo ""
echo "=== Service Endpoints ==="
kubectl get svc -A | head -20
kubectl get endpoints -A | head -20
```

### 快速诊断脚本 4: 存储状态检查

```bash
#!/bin/bash
# 存储状态快速检查
echo "=== PVC Status ==="
kubectl get pvc -A
kubectl get pv | grep -v Bound
echo ""
echo "=== CSI Driver Status ==="
kubectl get pods -n kube-system | grep csi
```

---

## 故障模式匹配流程

```
┌─────────────────────────────────────────────────────────────┐
│                    故障模式匹配流程                           │
├─────────────────────────────────────────────────────────────┤
│  1. 收集告警指标                                              │
│     ├── NodeStatus (NotReady, DiskPressure, MemoryPressure) │
│     ├── PodStatus (Pending, CrashLoopBackOff, Evicted)       │
│     ├── ServiceStatus (Endpoints 空缺)                       │
│     └── IngressStatus (5xx 错误率)                           │
│                                                              │
│  2. 匹配故障模式库                                            │
│     ├── ACK-001~ACK-022: 单一故障模式                        │
│     └── ACK-X001~ACK-X004: 级联故障模式                      │
│                                                              │
│  3. 诊断步骤执行                                              │
│     ├── 运行快速诊断脚本                                      │
│     ├── 收集相关指标                                          │
│     └── 确认根因                                              │
│                                                              │
│  4. 修复方案选择                                              │
│     ├── 根据严重等级排序                                      │
│     ├── 执行修复动作                                          │
│     └── 验证修复效果                                          │
│                                                              │
│  5. 跨 Skill 委托                                            │
│     ├── ECS 问题 → alicloud-ecs-ops                          │
│     ├── VPC 问题 → alicloud-vpc-ops                          │
│     ├── SLB 问题 → alicloud-slb-ops                          │
│     ├── RDS 问题 → alicloud-rds-ops                          │
│     └── OSS 问题 → alicloud-oss-ops                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 严重等级定义

| 等级 | 名称 | 响应时间 | 影响范围 | 示例 |
|------|------|----------|----------|------|
| P0 | Critical | 立即响应 | 集群级/全服务 | Node NotReady 风暴、CNI 异常、证书过期 |
| P1 | High | 15 分钟内 | 服务级/多 Pod | Pod 批量 CrashLoopBackOff、Ingress 502 |
| P2 | Medium | 1 小时内 | 单 Pod/单服务 | PVC Pending、镜像拉取失败 |
| P3 | Low | 4 小时内 | 配置级/非关键 | RBAC 配置优化、资源 Request 调整 |

---

## 预防措施清单

| 预防措施 | 适用故障模式 | 实施方式 |
|----------|-------------|----------|
| 多可用区部署 | ACK-001, ACK-002 | Node Pool 配置多 VSwitch |
| 资源预留 20% | ACK-002, ACK-007 | Node Pool 预留资源 |
| 证书自动轮换 | ACK-018 | 集群配置自动轮换 |
| CNI 版本升级 | ACK-010 | 定期升级 Terway/Flannel |
| HPA 配置 | ACK-002, ACK-005 | 应用配置 HPA |
| PDB 配置 | ACK-007 | 关键应用配置 PodDisruptionBudget |
| 监控告警 | 全部 | 配置 CMS 告警规则 |
| 资源 Request/Limit | ACK-002, ACK-006, ACK-009 | 所有 Pod 配置资源限制 |
| 就绪探针 | ACK-005, ACK-012 | 应用配置 readinessProbe |
| 存储自动扩容 | ACK-016 | StorageClass 配置 allowVolumeExpansion |

---

## 成本与资源浪费模式 (FinOps Patterns)

### ACK-F001 — 节点资源闲置浪费

| 属性 | 内容 |
|------|------|
| 触发指标 | Node `cpu.utilization` < 10% 持续 7 天 |
| 触发阈值 | CPU 使用率 < 10% AND 内存使用率 < 20% |
| 典型特征 | 节点运行但几乎无 Pod 调度，成本浪费 |
| 关联指标 | Node 上 Pod 数量 < 3, 节点池 `current_size` > `desired_size` |
| 根因 | 1. 业务迁移后未清理节点 2. 节点池配置过大 3. Pod 调度策略限制 4. 测试环境未关机 |
| 诊断步骤 | 1. `kubectl describe node` 查 Pod 分布 2. 查节点 7 天 CPU 平均使用率 3. 检查节点池配置 |
| 修复方案 | 1. 缩容节点池减少节点 2. 删除闲置节点 3. 切换到竞价实例降低成本 4. 关机非生产环境 |
| 预防措施 | 节点使用率告警、定期资源审计、自动缩容配置 |
| 严重等级 | P3-FinOps |
| 影响范围 | 成本级 |
| 预估损失 | ¥100-500/节点/月 |

### ACK-F002 — Pod 资源过度配置

| 属性 | 内容 |
|------|------|
| 触发指标 | Pod CPU Request > 实际使用 50% OR Memory Request > 实际使用 50% |
| 触发阈值 | 资源浪费率 > 50% 持续 3 天 |
| 典型特征 | Pod 请求大量资源但实际使用很低，成本浪费 |
| 关联指标 | Node 资源紧张但 Pod 实际使用低 |
| 根因 | 1. 开发时预估过高 2. 未根据实际使用调整 3. 复制粘贴配置 4. 缺乏资源审计 |
| 诊断步骤 | 1. `kubectl top pods` 查实际使用 2. `kubectl get pods -o yaml` 查请求配置 3. 计算浪费率 |
| 修复方案 | 1. 降低 CPU Request 到 P95 实际使用 2. 降低 Memory Request 到 P99 实际使用 3. 保持 Limit 作为峰值保护 |
| 预防措施 | 定期资源审计、VPA 自动调整、资源配置最佳实践培训 |
| 严重等级 | P3-FinOps |
| 影响范围 | 成本级/调度效率 |
| 预估损失 | ¥50-300/Pod/月 |

### ACK-F003 — PVC 存储过度配置

| 属性 | 内容 |
|------|------|
| 触发指标 | PVC Capacity > 实际使用 3x |
| 触发阈值 | 存储浪费率 > 200% |
| 典型特征 | PVC 申请大容量但实际使用很小 |
| 关联指标 | PVC 使用率监控、Pod 存储使用情况 |
| 根因 | 1. 开发时预估过高 2. 数据量增长低于预期 3. 未启用自动扩容 4. 复制配置模板 |
| 诊断步骤 | 1. `kubectl get pvc` 查容量配置 2. 查 PVC 实际使用率 3. 检查是否支持在线扩容 |
| 修复方案 | 1. 重建 PVC 调整容量（需数据迁移） 2. 启用 StorageClass 自动扩容 3. 设置容量告警阈值 |
| 预防措施 | StorageClass 自动扩容配置、存储使用率告警、定期存储审计 |
| 严重等级 | P3-FinOps |
| 影响范围 | 成本级 |
| 预估损失 | ¥0.35 × (容量-使用量) GB/月 |

### ACK-F004 — 闲置 PVC 未清理

| 属性 | 内容 |
|------|------|
| 触发指标 | PVC Bound 状态但无 Pod 挂载持续 7 天 |
| 触发阈值 | 闲置 PVC 数量 > 5 |
| 典型特征 | PVC 存在但未被任何 Pod 使用，持续计费 |
| 关联指标 | PV 状态、Pod 挂载情况 |
| 根因 | 1. Pod 删除后 PVC 未删除 2. 应用迁移后 PVC 遗留 3. 测试 PVC 未清理 |
| 诊断步骤 | 1. `kubectl get pvc -A` 列出所有 PVC 2. 检查 Pod 是否挂载该 PVC 3. 检查 PV 是否有数据 |
| 修复方案 | 1. 确认 PVC 无数据后删除 2. 删除关联 PV 和云盘 3. 定期 PVC 清理脚本 |
| 预防措施 | PVC 生命周期管理、应用部署时配置 PVC 清理策略、定期闲置资源检测 |
| 严重等级 | P3-FinOps |
| 影响范围 | 成本级 |
| 预估损失 | ¥0.35 × 容量 GB/月 |

### ACK-F005 — 成本异常激增

| 属性 | 内容 |
|------|------|
| 触发指标 | 集群日成本 > 基线 150% |
| 触发阈值 | 成本激增 > 50% 无业务增长支撑 |
| 典型特征 | 月账单突然大幅增长，无对应业务增长 |
| 关联指标 | 节点数量变化、Pod 数量变化、存储容量变化 |
| 根因 | 1. 节点池意外扩容 2. 竞价实例价格波动 3. 自动扩缩容配置异常 4. 测试环境未关机 5. 资源配置错误导致大量重建 |
| 诊断步骤 | 1. 查 Billing 详细账单 2. 对比节点数量变化时间线 3. 检查 Cluster Autoscaler 日志 4. 分析资源创建事件 |
| 修复方案 | 1. 缩容意外扩容的节点 2. 调整自动扩缩容上限 3. 关机测试环境 4. 修复资源配置错误 5. 优化竞价实例策略 |
| 预防措施 | 成本预算告警、扩缩容上限配置、竞价实例价格上限、环境生命周期管理 |
| 严重等级 | P2-FinOps |
| 影响范围 | 成本级 |
| 预估损失 | ¥500-5000/异常事件 |

### ACK-F006 — SLB 成本浪费

| 属性 | 内容 |
|------|------|
| 触发指标 | SLB 无后端健康服务器持续 24 小时 |
| 触发阈值 | 闲置 SLB 数量 > 3 |
| 典型特征 | SLB 实例存在但无流量转发，持续计费 |
| 关联指标 | Service LoadBalancer 类型、Ingress SLB 配置 |
| 根因 | 1. Service 删除后 SLB 未自动释放 2. 应用迁移后 SLB 遗留 3. 测试 SLB 未清理 4. SLB 保护机制阻止删除 |
| 诊断步骤 | 1. 查 SLB 后端健康状态 2. 检查 Service 是否关联该 SLB 3. 检查 Ingress 配置（委托 alicloud-slb-ops） |
| 修复方案 | 1. 解除 SLB 保护 2. 删除闲置 SLB 3. 清理关联 Service/Ingress |
| 预防措施 | Service annotations 配置 SLB 自动删除、定期 SLB 审计、测试环境生命周期管理 |
| 严重等级 | P3-FinOps |
| 影动范围 | 成本级 |
| 预估损失 | ¥20-200/SLB/月 |

### ACK-F007 — 竞价实例配置不当

| 属性 | 内容 |
|------|------|
| 触发指标 | 竞价实例中断率 > 30% OR 竞价实例节点池无混合配置 |
| 触发阈值 | 纯竞价实例节点池承载关键业务 |
| 典型特征 | 竞价实例频繁被回收导致服务中断，或成本节省未最大化 |
| 关联指标 | Node 状态变化频率、Pod 重启次数、节点池 Spot 配置 |
| 根因 | 1. 关键业务部署在纯竞价节点池 2. 竞价实例价格上限设置过低 3. 未配置多 AZ 分散风险 4. 未配置按量节点兜底 |
| 诊断步骤 | 1. 查节点池 Spot Strategy 配置 2. 检查竞价实例回收历史 3. 分析 Pod 分布和容忍配置 |
| 修复方案 | 1. 关键业务迁移到按量节点池 2. 配置混合节点池 (70% Spot + 30% On-demand) 3. 添加多 AZ 分布 4. 调整竞价实例价格上限 |
| 预防措施 | 混合节点池配置、多 AZ 分布、关键业务节点选择器、竞价实例回收告警 |
| 严重等级 | P2-FinOps |
| 影动范围 | 成本级/稳定性 |
| 预估损失 | 服务中断成本 > 成本节省 |

---

## FinOps 优化模式清单

| 优化模式 | 适用场景 | 预估节省 | 实施难度 |
|----------|----------|----------|----------|
| 节点规格优化 | CPU 使用率 30-60% 的节点池 | 20-40% | 低 |
| 竞价实例切换 | 无状态/批处理工作负载 | 50-90% | 中 |
| Pod Request 调整 | Request 远大于 Usage | 10-30% | 低 |
| 闲置资源清理 | 测试环境、遗留资源 | 100% | 低 |
| 存储容量优化 | PVC 过度配置 | 30-50% | 中 |
| 混合节点池配置 | 生产环境成本优化 | 20-40% | 中 |
| 自动缩容配置 | 业务波动大的集群 | 20-50% | 中 |

---

## FinOps 巡检脚本

```bash
#!/bin/bash
# ack-finops-inspection.sh
# Usage: ./ack-finops-inspection.sh <ClusterId> <RegionId>

CLUSTER_ID="$1"
REGION="$2"

echo "=== ACK FinOps Inspection Report ==="

# 1. Idle Nodes Detection
echo ""
echo "### Idle Nodes (CPU < 10% for 7 days) ###"
START=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

NODES=$(aliyun cs GET /clusters/$CLUSTER_ID/nodes | jq -r '.nodes[] | .instance_id')
IDLE_COUNT=0
for NODE_ID in $NODES; do
  CPU_AVG=$(aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName cpu.utilization \
    --Dimensions "[{\"instanceId\":\"$NODE_ID\"}]" \
    --Period 86400 \
    --StartTime "$START" \
    --EndTime "$END" \
    --output cols=Average rows=Datapoints[0].Average 2>/dev/null || echo "100")
  
  if [ $(echo "${CPU_AVG} < 10" | bc 2>/dev/null || echo 0) -eq 1 ]; then
    echo "  ⚠️  Idle Node: $NODE_ID (CPU: ${CPU_AVG}%)"
    IDLE_COUNT=$((IDLE_COUNT + 1))
  fi
done
echo "  Total Idle Nodes: $IDLE_COUNT"

# 2. Over-provisioned Pods
echo ""
echo "### Over-provisioned Pods (Request > Usage 50%) ###"
aliyun cs GET /k8s/$CLUSTER_ID/user_config > /tmp/kubeconfig
export KUBECONFIG=/tmp/kubeconfig

kubectl top pods -A --sort-by=cpu | head -20

# 3. Idle PVCs
echo ""
echo "### Idle PVCs (Bound but unused) ###"
kubectl get pvc -A -o json | jq -r '.items[] | select(.status.phase=="Bound") | "\(.metadata.namespace)/\(.metadata.name) - \(.spec.resources.requests.storage)"' | while read PVC; do
  NS=$(echo $PVC | cut -d'/' -f1)
  NAME=$(echo $PVC | cut -d'/' -f2 | cut -d' ' -f1)
  MOUNTED=$(kubectl get pods -n $NS -o json | jq --arg NAME "$NAME" '[.items[] | select(.spec.volumes[]?.persistentVolumeClaim?.claimName==$NAME)] | length')
  if [ "$MOUNTED" -eq 0 ]; then
    echo "  ⚠️  Idle PVC: $PVC (No pods mounting)"
  fi
done

# 4. Cost Summary
echo ""
echo "### Estimated Monthly Cost ###"
NODE_COUNT=$(echo "$NODES" | wc -l | tr -d ' ')
PVC_COUNT=$(kubectl get pvc -A --no-headers | wc -l | tr -d ' ')
echo "  Nodes: $NODE_COUNT × ¥150/month = ¥$((NODE_COUNT * 150))"
echo "  PVCs: $PVC_COUNT × ¥35/month (avg) = ¥$((PVC_COUNT * 35))"
echo "  Estimated Total: ¥$((NODE_COUNT * 150 + PVC_COUNT * 35))"

echo ""
echo "### Optimization Recommendations ###"
echo "1. Remove $IDLE_COUNT idle nodes → Save ¥$((IDLE_COUNT * 150))/month"
echo "2. Review Pod resource requests for over-provisioning"
echo "3. Clean up idle PVCs"
```

---

## FinOps 告警阈值建议

| 告警类型 | 指标 | 阈值 | 严重等级 | 响应 |
|----------|------|------|----------|------|
| 闲置节点 | Node CPU < 10% | 持续 7 天 | P3 | 缩容节点池 |
| 成本激增 | 日成本 > 基线 150% | 单日 | P2 | 检查扩缩容活动 |
| 闲置 PVC | PVC 无挂载 | 持续 7 天 | P3 | 清理 PVC |
| 存储浪费 | PVC 使用率 < 30% | 持续 3 天 | P3 | 缩容 PVC |
| 竞价回收 | Spot 节点中断 | > 3 次/小时 | P2 | 调整混合比例 |