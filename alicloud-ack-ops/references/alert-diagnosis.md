# Alert Diagnosis & Root Cause Analysis — Alibaba Cloud ACK

> This reference provides **intelligent diagnosis workflows**, **multi-dimensional correlation analysis**, **Kubernetes-specific diagnostic trees**, and **automated root-cause localization** for ACK alerts and cluster performance issues.

---

## 1. Alert-to-Root-Cause Correlation Matrix

When an alert fires, use this matrix to determine the most likely root causes and the diagnostic order.

### 1.1 Node Alerts

| Alert Condition | Primary Symptoms | Likely Root Causes | Diagnostic Order |
|-----------------|------------------|-------------------|------------------|
| Node NotReady > 30% | Nodes unreachable, Pods Evicted | 1. ECS instance failure<br>2. Kubelet crash<br>3. Network partition<br>4. Disk pressure (eviction)<br>5. Memory pressure (OOM) | 1. Check `NodeStatus` via CMS<br>2. Check ECS instance status (`alicloud-ecs-ops`)<br>3. Check `disk.utilization` and `memory.utilization`<br>4. Check kubelet logs via Cloud Assistant<br>5. Check VPC network connectivity |
| Node NotReady (single node) | Single node unreachable | 1. ECS instance stopped<br>2. Kubelet process crash<br>3. Certificate expired<br>4. Node resource exhaustion | 1. `DescribeClusterNodes` for node state<br>2. `DescribeInstances` for ECS status<br>3. Check node conditions (`DiskPressure`, `MemoryPressure`, `PIDPressure`) |
| Node CPU > 90% | Node CPU saturated | 1. Pod CPU throttling<br>2. System processes (kubelet, docker)<br>3. Malicious workload<br>4. Resource limit too high | 1. `kubectl top pods` on node<br>2. Check pod resource requests/limits<br>3. Check `cpu.utilization` via CMS<br>4. Check kubelet/docker CPU usage |
| Node Memory > 85% | Node memory pressure | 1. Pod memory leak<br>2. Too many pods on node<br>3. System memory leak<br>4. Buffer/cache not released | 1. `kubectl top pods` on node<br>2. Check pod restart count (OOMKilled)<br>3. Check `memory.utilization` via CMS<br>4. Check `MemoryPressure` condition |
| Node Disk > 90% | Disk pressure, Pod eviction | 1. Container images accumulation<br>2. Pod logs accumulation<br>3. EmptyDir volumes filling<br>4. System logs (journal, kubelet) | 1. `kubectl describe node` for `DiskPressure`<br>2. Cloud Assistant: `df -h /var/lib/docker`<br>3. Check image disk usage: `docker system df`<br>4. Check log sizes: `du -sh /var/log/*` |

### 1.2 Pod Alerts

| Alert Condition | Primary Symptoms | Likely Root Causes | Diagnostic Order |
|-----------------|------------------|-------------------|------------------|
| Pod CrashLoopBackOff > 5 pods | Pods repeatedly crashing | 1. Application code error<br>2. Configuration error (ConfigMap/Secret)<br>3. Missing dependency (DB, API)<br>4. Resource limit too low (OOM)<br>5. Image pull failure | 1. `kubectl logs pod-name --previous`<br>2. `kubectl describe pod` for events<br>3. Check `OOMKilled` in state<br>4. Check `ImagePullBackOff` status<br>5. Check ConfigMap/Secret existence |
| Pod Pending > 10 pods | Pods cannot be scheduled | 1. Insufficient node resources<br>2. Node selector/affinity mismatch<br>3. PVC pending (no PV)<br>4. Taints blocking scheduling<br>5. Quota exceeded | 1. `kubectl describe pod` for events<br>2. Check `FailedScheduling` reason<br>3. `kubectl top nodes` for resource availability<br>4. Check PVC status<br>5. Check node taints: `kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints` |
| Pod Evicted > threshold | Pods forcibly removed | 1. Node DiskPressure<br>2. Node MemoryPressure<br>3. Node NotReady<br>4. Pod resource limit exceeded | 1. Check node conditions<br>2. Check eviction reason in pod status<br>3. Check node resource usage<br>4. Review pod QoS class (Guaranteed/Burstable/BestEffort) |
| Pod RestartCount high | Pod frequently restarted | 1. Application crash<br>2. Liveness probe failure<br>3. OOMKilled<br>4. PreStop hook timeout<br>5. Init container failure | 1. `kubectl get pod -o jsonpath='{.status.containerStatuses[*].restartCount}'`<br>2. Check previous logs<br>3. Check liveness/readiness probe configuration<br>4. Check `lastState` in pod status |

### 1.3 Cluster Alerts

| Alert Condition | Primary Symptoms | Likely Root Causes | Diagnostic Order |
|-----------------|------------------|-------------------|------------------|
| Cluster CPU > 80% | Cluster-wide CPU saturation | 1. Traffic spike<br>2. Scale-out needed<br>3. Inefficient workload distribution<br>4. Missing resource limits | 1. CMS `CpuUsage` for cluster<br>2. `kubectl top pods --all-namespaces`<br>3. Check HPA status<br>4. Check node pool size<br>5. Delegate to `alicloud-ecs-ops` for node scaling |
| Cluster Memory > 85% | Cluster-wide memory pressure | 1. Memory leak in pods<br>2. Memory limits too high<br>3. Scale-out needed<br>4. Cached data not released | 1. CMS `MemoryUsage` for cluster<br>2. `kubectl top pods --all-namespaces`<br>3. Check pod restart count (OOMKilled)<br>4. Review pod memory limits |
| Cluster state != running | Cluster operation failed | 1. Creation failure (VPC/quota)<br>2. Upgrade failure<br>3. Scaling failure<br>4. Deletion in progress | 1. `DescribeClusterDetail` for state and error message<br>2. Check VPC/VSwitch existence<br>3. Check quota limits<br>4. Check addon status |
| API Server latency > 5s | Control plane slow | 1. Too many watch connections<br>2. Etcd performance issue<br>3. Leader election storm<br>4. Large cluster (many objects) | 1. Check `apiserver_request_duration_seconds` via Prometheus<br>2. Check etcd metrics<br>3. Review number of controllers<br>4. Consider cluster split or optimize controllers |

### 1.4 Addon Alerts

| Alert Condition | Primary Symptoms | Likely Root Causes | Diagnostic Order |
|-----------------|------------------|-------------------|------------------|
| Addon state != active | Addon malfunction | 1. Pod crash<br>2. Configuration error<br>3. Resource insufficient<br>4. Version incompatible | 1. `GET /clusters/{id}/addons` for addon status<br>2. Check addon pods in `kube-system`<br>3. Check addon logs<br>4. Check addon version compatibility |
| Ingress 5xx rate high | Ingress errors | 1. Backend pod unhealthy<br>2. Backend timeout<br>3. Ingress controller misconfiguration<br>4. SSL certificate issue | 1. Check Ingress controller logs<br>2. Check backend pod health<br>3. Check Service endpoints<br>4. Delegate to `alicloud-slb-ops` for SLB health |
| DNS resolution failure | CoreDNS issue | 1. CoreDNS pod crash<br>2. DNS configuration error<br>3. NetworkPolicy blocking<br>4. Node local DNS cache issue | 1. Check CoreDNS pods: `kubectl get pods -n kube-system -l k8s-app=kube-dns`<br>2. Check CoreDNS logs<br>3. Check CoreDNS ConfigMap<br>4. Test DNS from pod: `nslookup kubernetes.default` |

---

## 2. Multi-Dimensional Correlation Analysis

When multiple alerts fire simultaneously, use correlation analysis to identify the **primary root cause** vs **secondary effects**.

### 2.1 Correlation Matrix

| Symptom Combo | Primary Root Cause | Secondary Effects | Confirmation |
|---------------|-------------------|-------------------|--------------|
| Node NotReady↑ + Pod Pending↑ + Service timeout↑ | **Node failure cascade** | Pods unschedulable (pending), services inaccessible (timeout) | Multiple nodes NotReady simultaneously; ECS status abnormal |
| CPU↑ + Memory↑ + Pod CrashLoop↑ | **OOM/CPU throttle causing crash** | Pods crash (OOMKilled), CPU/memory high (retry attempts) | Pod logs show `OOMKilled`; restartCount > 0; resource limits at threshold |
| Pod CrashLoop↑ + ConfigMap change + New deployment | **ConfigMap/Secret update broke pods** | Pods crash after deployment, ConfigMap recently modified | Deployment timestamp matches pod crash start; `kubectl describe pod` shows ConfigMap error |
| Node Disk↑ + Pod Evicted↑ + New image deployed | **Large images filled disk** | Pods evicted (DiskPressure), disk high (image layers) | Recent image deployments; `docker system df` shows high image usage; `DiskPressure` condition True |
| Cluster CPU↑ + HPA not triggered + Node pool max | **HPA blocked by node pool limit** | CPU high, pods pending (cannot scale), node pool at max size | HPA desired > current; node pool max_size = current_size; `FailedScheduling` events |
| Ingress 5xx↑ + Backend pod 0/1 Ready + Service endpoints empty | **Backend pod failure** | Ingress 5xx, endpoints empty, pods not ready | `kubectl get endpoints` empty; backend pod `Ready` condition False |
| DNS failure + CoreDNS pod Pending + Node NotReady | **Node failure affecting DNS pods** | DNS unavailable, CoreDNS pending (cannot schedule), node NotReady | CoreDNS pod pending on NotReady node; other pods also pending |
| Cluster state failed + VPC not found + CreateCluster | **VPC creation failed** | Cluster creation failed, VPC/VSwitch missing | `DescribeClusterDetail` shows VPC error; `DescribeVpcs` returns empty for target VPC |

### 2.2 Dimensional Analysis Decision Tree

```
收到多维度告警
│
├─ Node NotReady 高?
│  ├─ 多节点同时NotReady?
│  │  ├─ ECS状态异常? → 根因: 底层ECS故障/VPC网络分区
│  │  │  └─ 行动: 委托 alicloud-ecs-ops + alicloud-vpc-ops
│  │  └─ ECS状态正常? → 根因: Kubelet/Docker异常
│  │     └─ 行动: 通过Cloud Assistant检查kubelet日志,重启服务
│  ├─ 单节点NotReady?
│  │  ├─ DiskPressure=True? → 根因: 磁盘空间不足
│  │  │  └─ 行动: 清理镜像/日志,扩容磁盘
│  │  ├─ MemoryPressure=True? → 根因: 内存不足
│  │  │  └─ 行动: 驱逐低优先级Pod,扩容节点
│  │  └─ KubeletNotReady? → 根因: Kubelet证书过期或进程异常
│  │     └─ 行动: 检查kubelet证书,重启kubelet
│
├─ Pod CrashLoopBackOff 高?
│  ├─ OOMKilled?
│  │  ├─ 单PodOOM? → 根因: 该Pod内存泄漏或limit太低
│  │  │  └─ 行动: 分析Pod内存使用,调高limit或修复泄漏
│  │  └─ 多PodOOM? → 根因: 节点内存不足或limit配置错误
│  │     └─ 行动: 检查节点内存,批量调整Pod limit
│  ├─ ImagePullBackOff?
│  │  ├─ 单Pod失败? → 根因: 镜像不存在或认证失败
│  │  │  └─ 行动: 检查镜像tag,imagePullSecret
│  │  └─ 多Pod失败? → 根因: 镜像仓库不可达
│  │     └─ 行动: 检查网络连通性,镜像仓库状态
│  ├─ ConfigMap/Secret error? → 根因: 配置项不存在或格式错误
│  │  └─ 行动: 检查ConfigMap/Secret存在性和内容
│  └─ Application error? → 根因: 代码bug或依赖服务不可用
│     └─ 行动: 分析应用日志,检查依赖服务状态
│
├─ Pod Pending 高?
│  ├─ Insufficient cpu/memory?
│  │  ├─ 节点资源确实不足? → 根因: 需要扩容节点池
│  │  │  └─ 行动: ScaleOutCluster或创建新NodePool
│  │  └─ Pod request过高? → 根因: 资源request配置不合理
│  │     └─ 行动: 调整Pod资源request,优化调度
│  ├─ NodeSelector/Affinity mismatch? → 根因: 调度约束不匹配
│  │  └─ 行动: 检查节点label,调整Pod调度策略
│  ├─ PVC Pending? → 根因: PV不足或StorageClass问题
│  │  └─ 行动: 检查PV/StorageClass,创建新PV或调整PVC
│  └─ Taint blocking? → 根因: 污点阻止调度
│     └─ 行动: 检查节点污点,添加容忍或去除污点
│
├─ Cluster CPU/Memory 高?
│  ├─ HPA已触发但Pod Pending? → 根因: NodePool容量不足
│  │  └─ 行动: 扩容NodePool,启用Cluster Autoscaler
│  ├─ HPA未触发? → 根因: HPA配置问题或metrics-server异常
│  │  └─ 行动: 检查HPA配置,验证metrics-server运行
│  └─ 无HPA配置? → 根因: 缺少自动扩缩容机制
│     └─ 行动: 配置HPA,设置合理阈值
│
├─ Ingress/Service 异常?
│  ├─ Endpoints empty? → 根因: Pod不匹配Service selector
│  │  └─ 行动: 检查Pod label和Service selector匹配
│  ├─ Endpoints有Pod但Pod NotReady? → 根因: Pod未通过readiness probe
│  │  └─ 行动: 检查Pod readinessProbe配置和应用健康
│  ├─ SLB健康检查失败? → 根因: 后端响应异常
│  │  └─ 行动: 委托 alicloud-slb-ops 检查SLB配置
│  └─ NetworkPolicy blocking? → 根因: 网络策略阻止流量
│     └─ 行动: 检查NetworkPolicy规则,调整策略
│
└─ Addon 异常?
   ├─ CoreDNS异常? → 根因: DNS Pod问题或配置错误
   │  └─ 行动: 检查CoreDNS Pod状态和ConfigMap
   ├─ Ingress Controller异常? → 根因: Ingress Pod问题或配置错误
   │  └─ 行动: 检查Ingress Controller Pod和配置
   └─ Prometheus异常? → 根因: 监控采集器问题或存储不足
      └─ 行动: 检查Prometheus Pod状态和存储
```

---

## 3. Kubernetes-Specific Diagnostic Trees

### 3.1 Pod Diagnostic Tree

```
Pod 故障诊断
│
├─ 状态 = Pending
│  ├─ describe pod → Events
│  │  ├─ "0/N nodes are available" → 检查节点总数,是否有Ready节点
│  │  ├─ "Insufficient cpu" → Pod CPU request > 节点可用CPU
│  │  │  └─ 行动: 降低 request 或扩容节点池
│  │  ├─ "Insufficient memory" → Pod Memory request > 节点可用Memory
│  │  │  └─ 行动: 降低 request 或扩容节点池
│  │  ├─ "node(s) didn't match node selector" → 节点label不匹配
│  │  │  └─ 行动: 检查 nodeSelector 配置和节点 label
│  │  ├─ "node(s) had taints that the pod didn't tolerate" → 污点容忍问题
│  │  │  └─ 行动: 添加 tolerations 或去除节点污点
│  │  ├─ "persistentvolumeclaim ... not bound" → PVC未绑定
│  │  │  └─ 行动: 检查 PV 和 StorageClass
│  │  └─ "pod has unbound immediate PersistentVolumeClaims" → PVC等待
│  │     └─ 行动: 创建 PV 或等待动态创建
│
├─ 状态 = CrashLoopBackOff
│  ├─ 获取 previous logs: kubectl logs pod --previous
│  │  ├─ "OOMKilled" → 内存不足
│  │  │  └─ 行动: 增加 memory limit 或修复内存泄漏
│  │  ├─ "Error" exit code → 应用错误
│  │  │  └─ 行动: 分析应用日志,修复代码
│  │  ├─ "ContainerCreating" timeout → 镜像拉取慢或init container卡住
│  │  │  └─ 行动: 检查镜像大小和网络,检查 init container
│  │  └─ "ImagePullBackOff" → 镜像问题
│  │     ├─ "image ... not found" → 镜像不存在
│  │     ├─ "failed to authorize" → imagePullSecret无效
│  │     └─ "connection refused" → 镜像仓库不可达
│  ├─ describe pod → Events
│  │  ├─ Liveness probe failed → 存活探针失败
│  │  │  └─ 行动: 检查探针配置和应用响应
│  │  ├─ Readiness probe failed → 就绪探针失败
│  │  │  └─ 行动: 检查探针配置和依赖服务
│  │  └─ Back-off restarting failed container → 反复重启
│  │     └─ 行动: 深入分析日志和配置
│
├─ 状态 = Evicted
│  ├─ describe pod → Status
│  │  ├─ Reason: "Evicted" → 节点压力驱逐
│  │  ├─ Message: "The node was low on resource: ..." → 具体资源类型
│  │  │  ├─ "ephemeral-storage" → 磁盘压力
│  │  │  ├─ "memory" → 内存压力
│  │  │  └─ "pid" → 进程数压力
│  │  └─ 行动: 扩容节点池,清理资源,或调整Pod QoS
│
├─ 状态 = Running but Not Ready (0/1 Ready)
│  ├─ describe pod → Conditions
│  │  ├─ Ready = False
│  │  │  ├─ Reason: "ContainersNotReady" → 容器未就绪
│  │  │  │  └─ 检查容器状态和readiness probe
│  │  │  └─ Reason: "PodCompleted" → Job执行完成(正常)
│  │  └─ ContainersReady = False
│  │     ├─ 容器仍在启动 → 等待启动完成
│  │     └─ readiness probe失败 → 检查探针配置
│  └─ get endpoints → 检查是否已加入Service endpoints
│
└─ 状态 = Terminating (长时间)
   ├─ describe pod → Events
   │  ├─ "preStop hook failed" → PreStop hook执行失败或超时
   │  ├─ "container ... is not dead" → 容器无法停止
   │  └─ 行动: 强制删除或检查PreStop hook
```

### 3.2 Node Diagnostic Tree

```
Node 故障诊断
│
├─ 状态 = NotReady
│  ├─ describe node → Conditions
│  │  ├─ DiskPressure = True
│  │  │  ├─ df -h /var/lib/docker → 检查容器磁盘
│  │  │  ├─ df -h /var/log → 检查日志磁盘
│  │  │  ├─ docker system df → 检查镜像占用
│  │  │  └─ 行动: 清理镜像/日志/未使用容器
│  │  ├─ MemoryPressure = True
│  │  │  ├─ top pods → 检查Pod内存使用
│  │  │  ├─ free -h → 检查系统内存
│  │  │  └─ 行动: 驱逐低优先级Pod,扩容节点
│  │  ├─ PIDPressure = True
│  │  │  ├─ ps aux | wc -l → 检查进程数
│  │  │  └─ 行动: 检查异常进程,减少Pod密度
│  │  ├─ NetworkUnavailable = True
│  │  │  ├─ 检查 CNI Pod (Terway/Flannel)
│  │  │  ├─ 检查 VPC ENI 配额
│  │  │  └─ 行动: 重启CNI Pod,申请ENI配额
│  │  ├─ KubeletHasSufficientMemory = False
│  │  │  └─ Kubelet内存不足 → 行动: 重启kubelet或扩容节点
│  │  ├─ KubeletHasNoDiskPressure = False
│  │  │  └─ Kubelet磁盘不足 → 行动: 清理kubelet数据目录
│  │  └─ KubeletHasSufficientPID = False
│  │     └─ Kubelet进程数不足 → 行动: 检查kubelet进程状态
│  │
│  ├─ ECS状态检查 (委托 alicloud-ecs-ops)
│  │  ├─ Status != Running → ECS实例问题
│  │  │  └─ 行动: 启动实例或排查ECS故障
│  │  ├─ Status = Running但Node NotReady → Kubelet/Docker问题
│  │  │  ├─ systemctl status kubelet → 检查kubelet服务
│  │  │  ├─ systemctl status docker → 检查docker服务
│  │  │  ├─ journalctl -u kubelet → 检查kubelet日志
│  │  │  └─ 行动: 重启服务或修复配置
│  │  └─ 网络连通性检查
│  │     ├─ ping API Server → 检查到控制平面连通性
│  │     ├─ ping other nodes → 检查节点间连通性
│  │     └─ 行动: 检查VPC/安全组配置
│
├─ 状态 = Ready但性能异常
│  ├─ CPU使用率高
│  │  ├─ top pods → 找出高CPU Pod
│  │  ├─ top → 找出高CPU进程
│  │  ├─ kubelet/docker CPU高? → 系统组件问题
│  │  └─ 行动: 优化Pod或扩容节点
│  ├─ 内存使用率高
│  │  ├─ top pods → 找出高内存Pod
│  │  ├─ 检查Pod restart count → OOMKilled?
│  │  └─ 行动: 调整Pod limit或扩容节点
│  └─ 网络流量异常
│     ├─ 检查Pod网络流量
│     ├─ 检查iptables规则数
│     └─ 行动: 检查NetworkPolicy或网络插件配置
│
└─ 状态=SchedulingDisabled (Cordoned)
   ├─ kubectl uncordon node → 解除封锁
   ├─ 检查封锁原因 → 维护/调试?
   └─ 行动: 完成维护后解除封锁
```

### 3.3 Network/Service Diagnostic Tree

```
网络/Service 故障诊断
│
├─ DNS解析失败
│  ├─ nslookup kubernetes.default → 测试集群内DNS
│  │  ├─ 解析成功 → Pod内DNS客户端问题
│  │  ├─ 解析失败 → CoreDNS问题
│  │  │  ├─ kubectl get pods -n kube-system -l k8s-app=kube-dns
│  │  │  │  ├─ CoreDNS Pod Running → 检查CoreDNS ConfigMap
│  │  │  │  ├─ CoreDNS Pod Pending → 节点资源不足或调度问题
│  │  │  │  ├─ CoreDNS Pod CrashLoopBackOff → CoreDNS配置错误
│  │  │  │  └─ 行动: 重启CoreDNS Pod或修复配置
│  │  └─ 解析慢 → DNS缓存问题或网络延迟
│  │     └─ 行动: 检查节点本地DNS缓存或CoreDNS配置
│  │
│  ├─ kubectl exec pod -- nslookup external.domain → 测试外部DNS
│  │  ├─ 解析成功 → 内部DNS配置问题
│  │  ├─ 解析失败 → 外部DNS不可达
│  │  │  └─ 检查 /etc/resolv.conf 或节点DNS配置
│  │  └─ 行动: 配置CoreDNS上游DNS服务器
│
├─ Service访问失败
│  ├─ kubectl get endpoints service-name → 检查Endpoints
│  │  ├─ Endpoints empty → 没有匹配的Pod
│  │  │  ├─ 检查Service selector → 与Pod label匹配?
│  │  │  ├─ 检查Pod状态 → Running且Ready?
│  │  │  └─ 行动: 修复Pod label或Pod状态
│  │  ├─ Endpoints有内容但访问失败
│  │  │  ├─ curl endpointIP:port → 测试直连Pod
│  │  │  │  ├─ 成功 → Service代理问题(kube-proxy)
│  │  │  │  └─ 失败 → Pod应用问题
│  │  │  └─ 行动: 检查kube-proxy Pod和应用日志
│  │  └─ Endpoints不稳定 → Pod频繁重启
│  │     └─ 行动: 检查Pod稳定性
│  │
│  ├─ ClusterIP Service测试
│  │  ├─ curl clusterIP:port → 测试ClusterIP
│  │  │  ├─ 成功 → Service正常
│  │  │  ├─ 失败 → kube-proxy问题或iptables规则
│  │  └─ 行动: 检查kube-proxy和iptables
│  │
│  └─ NodePort Service测试
│     ├─ curl nodeIP:nodePort → 测试NodePort
│     │  ├─ 成功 → Service正常
│     │  ├─ 失败 → 安全组未放行NodePort
│     └─ 行动: 检查安全组规则
│
├─ Ingress访问失败
│  ├─ kubectl get ingress → 检查Ingress配置
│  │  ├─ ADDRESS empty → Ingress Controller未分配IP/SLB
│  │  │  └─ 检查Ingress Controller Pod和SLB状态
│  │  ├─ ADDRESS有值但访问失败
│  │  │  ├─ curl ingressIP/path → 测试Ingress
│  │  │  │  ├─ 404 → 路径配置错误
│  │  │  │  ├─ 502 → Backend Pod不健康
│  │  │  │  ├─ 503 → Backend Pod不存在
│  │  │  │  ├─ SSL错误 → 证书问题
│  │  │  │  └─ 行动: 修复Ingress配置或Backend
│  │  └─ 委托 alicloud-slb-ops 检查SLB健康
│  │
│  ├─ Ingress Controller Pod状态
│  │  ├─ Running → 检查Controller日志
│  │  ├─ CrashLoopBackOff → Controller配置错误
│  │  └─ Pending → 节点资源不足
│  │  └─ 行动: 修复Controller状态
│  │
│  └─ NetworkPolicy检查
│     ├─ kubectl get networkpolicy -n namespace
│     ├─ 检查策略是否阻止必要流量
│     └─ 行动: 调整NetworkPolicy规则
│
└─ 跨Namespace通信失败
   ├─ 检查NetworkPolicy是否限制跨Namespace
   ├─ 检查Service是否正确配置(同Namespace或跨Namespace)
   └─ 行动: 检查NetworkPolicy和Service配置
```

### 3.4 Storage/PVC Diagnostic Tree

```
Storage/PVC 故障诊断
│
├─ PVC状态 = Pending
│  ├─ kubectl describe pvc → Events
│  │  ├─ "no persistent volumes available" → 没有可用PV
│  │  │  ├─ 检查PV是否存在 → kubectl get pv
│  │  │  ├─ 检查StorageClass → kubectl get storageclass
│  │  │  └─ 行动: 创建PV或配置StorageClass动态创建
│  │  ├─ "storageclass.storage.k8s.io \"xxx\" not found" → StorageClass不存在
│  │  │  └─ 行动: 创建StorageClass
│  │  ├─ "exceeded quota" → 存储配额不足
│  │  │  └─ 行动: 申请配额或调整PVC大小
│  │  └─ "waiting for a volume to be created" → 等待动态创建
│  │     └─ 行动: 检查Provisioner Pod状态
│  │
│  ├─ StorageClass检查
│  │  ├─ kubectl get storageclass xxx -o yaml
│  │  │  ├─ provisioner字段 → 确认Provisioner类型
│  │  │  ├─ NFS/CloudNAS → 检查NAS服务状态
│  │  │  ├─ alicloud-disk → 检查云盘配额
│  │  │  ├─ OSS → 检查OSS Bucket状态
│  │  │  └─ 行动: 委托相关skill检查后端存储
│  │  └─ Provisioner Pod检查
│  │     ├─ kube-system namespace → 找Provisioner Pod
│  │     ├─ Pod状态异常 → 重启或修复
│  │     └─ 行动: 修复Provisioner
│
├─ PVC状态 = Bound但挂载失败
│  ├─ describe pod → Events
│  │  ├─ "MountVolume.SetUp failed" → 挂载失败
│  │  │  ├─ 检查PV accessModes → 与PVC匹配?
│  │  │  ├─ 检查节点与存储位置 → 同Zone/Region?
│  │  │  ├─ 检查存储服务状态 → NAS/OSS/云盘正常?
│  │  │  └─ 行动: 修复存储配置或节点调度
│  │  ├─ "volume is already exclusively attached" → 云盘已挂其他节点
│  │  │  └─ 行动: 等待云盘释放或强制卸载
│  │  └─ "failed to mount" → 挂载命令失败
│  │     ├─ 检查节点mount工具
│  │     ├─ 检查存储权限
│  │     └─ 行动: 修复节点环境或存储权限
│  │
│  └─ Pod内挂载检查
│     ├─ mount | grep pvc → 检查挂载点
│     ├─ ls mountpoint → 检查数据可访问
│     └─ 行动: 检查存储数据和权限
│
└─ PVC状态 = Lost
   ├─ PV状态检查 → kubectl get pv
   │  ├─ PV Released → 需要回收或重建
   │  ├─ PV Failed → 存储后端问题
   │  └─ 行动: 检查存储后端,回收PV
   └─ 行动: 修复PV或重建PVC
```

---

## 4. Time-Series Analysis Patterns

When analyzing metrics over time, identify these patterns to guide diagnosis:

### 4.1 Pattern Recognition Guide

| Pattern | Visual Shape | Likely Cause | Diagnostic Action |
|---------|-------------|--------------|-------------------|
| **Sudden Spike** | 瞬间垂直上升后恢复 | 单次大任务(批量Job), Pod重启风暴, 部署事件 | 检查对应时间窗口的Pod事件和Job执行记录 |
| **Gradual Ramp** | 缓慢持续上升 | 业务增长, 数据积累, Pod数量增加 | 对比7天/30天趋势; 检查Pod数量变化; 检查HPA触发记录 |
| **Periodic Wave** | 规律性波峰波谷 | 定时Job执行, 定时备份, 批处理任务 | 检查CronJob配置; 关联备份执行时间; 检查定时任务日志 |
| **Step Change** | 阶梯式跳跃后平稳 | 新应用部署, 配置变更, Node Pool扩缩容 | 检查Deployment更新时间; 检查Node Pool变更记录 |
| **Sawtooth** | 锯齿状反复升降 | Pod频繁重启/驱逐, 自动扩缩容反复触发 | 检查Pod restartCount; 检查HPA配置稳定性 |
| **Flatline High** | 持续高位平稳 | 持续高负载, 资源配置不足, 缺少扩缩容机制 | 检查HPA配置; 检查Node Pool容量; 建议扩容 |
| **Cascade Pattern** | 多指标同步变化 | 根因导致连锁反应 (Node故障→Pod Pending→Service异常) | 按时间顺序追溯最早变化的指标 |
| **Correlation with External Event** | 与业务事件同步 | 促销活动, 大流量涌入, 外部API调用高峰 | 关联业务日历; 检查外部依赖调用日志 |

### 4.2 Baseline Deviation Analysis

```
基线偏离分析流程
│
├─ 获取当前指标值 (Current)
│  ├─ CMS实时指标: DescribeMetricList
│  └─ kubectl实时状态: top nodes/pods
│
├─ 获取历史基线 (Baseline)
│  ├─ 同时间段昨天 (D-1)
│  ├─ 同时间段上周同一天 (W-1)
│  ├─ 同时间段上月同一天 (M-1)
│  └─ 集群创建后的平均水平 (Cluster baseline)
│
├─ 计算偏离度
│  ├─ Deviation = (Current - Baseline) / Baseline * 100%
│  ├─ 偏离度 > 50% → 显著异常, 需立即调查
│  ├─ 偏离度 20-50% → 中度异常, 需关注趋势
│  └─ 偏离度 < 20% → 正常波动
│
└─ 判断异常类型
   ├─ D-1 和 W-1 同时偏离 → 系统性问题 (配置变更/应用变更/节点故障)
   ├─ 仅 D-1 偏离 → 短期问题 (单次Job/临时任务/单Pod异常)
   ├─ 仅 W-1 偏离 → 周期性业务变化 (周末效应/月末报表)
   └─ 新基线形成 → 业务增长或架构变更, 需调整监控阈值
```

### 4.3 Time-Series Correlation Queries

```bash
# 查询集群CPU使用趋势(过去1小时)
aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"clusterId":"c-xxx"}]' \
  --StartTime "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \
  --EndTime "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --Period 60

# 查询Pod重启次数趋势(通过Event统计)
kubectl get events --all-namespaces \
  --field-selector reason=BackOff \
  --sort-by='.lastTimestamp' \
  -o json | jq '[.items[] | {time: .lastTimestamp, pod: .involvedObject.name, namespace: .involvedObject.namespace}]'

# 查询节点NotReady时间线
kubectl get events --all-namespaces \
  --field-selector reason=NodeNotReady \
  --sort-by='.lastTimestamp'
```

---

## 5. Automated Diagnosis Workflow

### 5.1 Smart Alert Response Workflow

When user reports an alert (e.g., "ACK节点NotReady告警"), Agent executes the following automated diagnosis workflow:

#### Phase 1: Alert Triage (30 seconds)

```
1. 获取集群基本信息
   → DescribeClusterDetail
   → 确认 ClusterId, State, Version, NodeCount

2. 获取集群性能快照
   → CMS DescribeMetricList (CpuUsage, MemoryUsage, NodeStatus)
   → DescribeClusterNodes (节点列表和状态)

3. 判断告警严重程度
   ├─ 集群状态 != running → Critical, 优先处理集群状态
   ├─ Node NotReady > 30% → Critical, 立即深入诊断
   ├─ Pod CrashLoopBackOff > 20 pods → Critical
   ├─ CPU > 85% OR Memory > 90% → High, 标准诊断流程
   └─ 其他 → Warning, 标准诊断流程
```

#### Phase 2: Multi-Dimensional Correlation (60 seconds)

```
4. 根据告警类型, 执行关联检查
   ├─ Node NotReady 告警 → 同时获取:
   │  ├─ ECS实例状态 (alicloud-ecs-ops)
   │  ├─ VPC网络状态 (alicloud-vpc-ops)
   │  ├─ CMS cpu/memory/disk指标
   │  └─ kube-system namespace Pod状态
   │
   ├─ Pod CrashLoopBackOff 告警 → 同时获取:
   │  ├─ Pod日志 (kubectl logs --previous)
   │  ├─ Pod Events (kubectl describe pod)
   │  ├─ ConfigMap/Secret状态
   │  └─ Deployment/StatefulSet状态
   │
   ├─ Cluster CPU/Memory 告警 → 同时获取:
   │  ├─ HPA状态 (kubectl get hpa --all-namespaces)
   │  ├─ Node Pool状态 (GET /clusters/{id}/nodepools)
   │  ├─ Pod资源使用 (kubectl top pods --all-namespaces)
   │  └─ CMS集群级指标趋势
   │
   └─ Ingress/Service 告警 → 同时获取:
      ├─ Endpoints状态 (kubectl get endpoints)
      ├─ SLB健康状态 (alicloud-slb-ops)
      ├─ Ingress Controller Pod状态
      └─ NetworkPolicy配置

5. 应用关联矩阵 (Section 2.1)
   → 识别 Primary Root Cause vs Secondary Effects
```

#### Phase 3: Kubernetes-Specific Deep Dive (90 seconds)

```
6. 执行Kubernetes特定诊断
   ├─ Node诊断 → describe node, 检查Conditions
   │  ├─ DiskPressure → 检查磁盘使用
   │  ├─ MemoryPressure → 检查内存使用
   │  ├─ NetworkUnavailable → 检查CNI Pod
   │  └─ Kubelet问题 → Cloud Assistant检查kubelet日志
   │
   ├─ Pod诊断 → describe pod, logs, events
   │  ├─ Pending → 检查调度事件
   │  ├─ CrashLoopBackOff → 分析previous日志
   │  ├─ Evicted → 检查驱逐原因
   │  └─ NotReady → 检查probe配置
   │
   ├─ Service诊断 → endpoints, ingress, networkpolicy
   │  ├─ Endpoints空 → 检查selector匹配
   │  ├─ SLB异常 → 委托alicloud-slb-ops
   │  └─ DNS失败 → 检查CoreDNS Pod
   │
   └─ Storage诊断 → PVC/PV状态
      ├─ PVC Pending → 检查StorageClass
      ├─ 挂载失败 → 检查节点Zone和存储位置
      └─ 读写异常 → 检查存储后端服务

7. 获取时间窗口内的详细事件
   → kubectl get events --all-namespaces --sort-by='.lastTimestamp'
   → 分析事件时间线,追溯根因触发点
```

#### Phase 4: Root Cause Synthesis (30 seconds)

```
8. 综合分析所有数据, 生成诊断报告
   ├─ 根因分类: [节点故障] / [Pod配置] / [资源不足] / [网络问题] / [存储问题] / [应用错误]
   ├─ 影响评估: [仅性能下降] / [有服务中断风险] / [有数据风险]
   └─ 建议行动: [重启服务] / [扩容节点池] / [调整配置] / [修复应用] / [联系阿里云支持]

9. 输出结构化诊断结果
   ├─ 告警摘要
   ├─ 根因分析 (含证据链)
   ├─ 影响评估
   ├─ 即时建议 (可立即执行)
   └─ 长期建议 (需计划执行)
```

### 5.2 Diagnosis Report Template

```markdown
## ACK 智能诊断报告

### 集群信息
- ClusterId: {{user.cluster_id}}
- 集群名称: {{cluster_name}}
- 状态: {{cluster_state}}
- Kubernetes版本: {{k8s_version}}
- 节点数: {{node_count}} (Ready: {{ready_count}}, NotReady: {{notready_count}})

### 告警摘要
- 告警类型: {{alert_type}}
- 触发时间: {{alert_time}}
- 当前值: {{current_value}} (阈值: {{threshold}})
- 告警来源: {{alert_source}} (CMS / Prometheus / 自定义)

### 根因分析
**主要根因**: {{primary_root_cause}}
**置信度**: {{confidence}}%
**证据链**:
1. {{evidence_1}} (时间: {{time_1}})
2. {{evidence_2}} (时间: {{time_2}})
3. {{evidence_3}} (时间: {{time_3}})

**次要影响**:
- {{secondary_effect_1}}
- {{secondary_effect_2}}

### 影响评估
- 集群可用性影响: {{availability_impact}} (正常运行/部分降级/完全不可用)
- Pod影响范围: {{pod_impact}} ({{affected_pod_count}} pods受影响)
- 服务影响范围: {{service_impact}} ({{affected_service_count}} services受影响)
- 数据风险: {{data_risk}} (无风险/PVC风险/数据丢失风险)

### 即时建议 (可立即执行)
1. {{immediate_action_1}}
   ```bash
   {{immediate_command_1}}
   ```
2. {{immediate_action_2}}
   ```bash
   {{immediate_command_2}}
   ```

### 长期建议
1. {{long_term_action_1}} — 预计收益: {{benefit_1}}
2. {{long_term_action_2}} — 预计收益: {{benefit_2}}

### 相关诊断命令
```bash
# 验证诊断结果
kubectl describe node {{node_name}}
kubectl logs {{pod_name}} -n {{namespace}} --previous --tail=100
kubectl get events --field-selector involvedObject.name={{pod_name}} --sort-by='.lastTimestamp'

# 集群健康状态
aliyun cs GET /clusters/{{cluster_id}}/nodes | jq '.nodes[] | {instance_id, state, node_status}'
aliyun cms DescribeMetricList --Namespace acs_k8s_dashboard --MetricName CpuUsage --Dimensions '[{"clusterId":"{{cluster_id}}"}]'
```

### API调用统计
{{api_call_summary}}
```

---

## 6. Common Failure Scenario Playbooks

### 6.1 Scenario: "Node NotReady风暴"

**症状**: 多个节点(>30%)同时NotReady, Pod大量Pending/Evicted, 服务中断

**诊断剧本**:

```bash
# Step 1: 获取节点状态分布 (10s)
aliyun cs GET /clusters/{{cluster_id}}/nodes | jq '
  .nodes | group_by(.node_status) | map({status: .[0].node_status, count: length})'

# Step 2: 获取NotReady节点详情 (20s)
aliyun cs GET /clusters/{{cluster_id}}/nodes | jq '
  .nodes[] | select(.node_status != "Ready") | {instance_id, node_name, state, node_status}' \
  > /tmp/notready_nodes.json

# Step 3: 检查ECS实例状态 (委托 alicloud-ecs-ops) (30s)
# 批量查询NotReady节点的ECS状态
INSTANCE_IDS=$(jq -r '.[].instance_id' /tmp/notready_nodes.json | tr '\n' ',' | sed 's/,$//')
aliyun ecs DescribeInstances \
  --RegionId "{{region}}" \
  --InstanceIds "[\"$INSTANCE_IDS\"]" \
  --output cols=InstanceId,Status,InstanceType rows=Instances.Instance[].{InstanceId,Status,InstanceType}

# Step 4: 获取kubeconfig并检查节点Conditions (20s)
aliyun cs GET /k8s/{{cluster_id}}/user_config > /tmp/ack-kubeconfig
export KUBECONFIG=/tmp/ack-kubeconfig

for NODE in $(jq -r '.[].node_name' /tmp/notready_nodes.json); do
  echo "=== Node: $NODE ==="
  kubectl describe node "$NODE" | grep -A10 "Conditions:"
done

# Step 5: 检查CMS指标趋势 (20s)
START_TIME=$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

for INSTANCE_ID in $(jq -r '.[].instance_id' /tmp/notready_nodes.json); do
  aliyun cms DescribeMetricList \
    --Namespace acs_ecs_dashboard \
    --MetricName cpu.utilization \
    --Dimensions "[{\"instanceId\":\"$INSTANCE_ID\"}]" \
    --StartTime "$START_TIME" \
    --EndTime "$END_TIME" \
    --Period 60 | jq '.Datapoints[-5:]'
done
```

**根因判断**:
- 如果多数ECS实例 `Status` != `Running` → **根因: 底层ECS故障**
- 如果ECS `Status` = `Running` 但 kubelet Conditions 异常 → **根因: Kubelet/Docker异常**
- 如果 `DiskPressure` = True 节点最多 → **根因: 磁盘空间耗尽**
- 如果 `NetworkUnavailable` = True → **根因: VPC网络分区或CNI故障**
- 如果ECS和Conditions都正常 → **根因: API Server连接问题或证书过期**

**即时行动**:
1. ECS故障 → 委托 `alicloud-ecs-ops` 修复或替换实例
2. Kubelet异常 → 通过Cloud Assistant重启kubelet: `systemctl restart kubelet`
3. 磁盘满 → 清理镜像和日志: `docker system prune -af && rm -rf /var/log/pods/*`
4. 网络问题 → 检查VPC路由和安全组,委托 `alicloud-vpc-ops`
5. 证书问题 → 检查kubelet证书有效期,必要时轮换

---

### 6.2 Scenario: "Pod CrashLoopBackOff风暴"

**症状**: 大量Pod(>20)处于CrashLoopBackOff状态,应用不可用

**诊断剧本**:

```bash
# Step 1: 获取CrashLoopBackOff Pod列表 (10s)
kubectl get pods --all-namespaces --field-selector status.phase=Pending \
  -o json | jq '.items[] | select(.status.containerStatuses[]?.state.waiting?.reason == "CrashLoopBackOff") | {name: .metadata.name, namespace: .metadata.namespace, restartCount: .status.containerStatuses[0].restartCount}' \
  > /tmp/crashloop_pods.json

# Step 2: 分析前5个Pod的日志 (40s)
for i in 1 2 3 4 5; do
  POD=$(jq -r ".[$i-1].name" /tmp/crashloop_pods.json)
  NS=$(jq -r ".[$i-1].namespace" /tmp/crashloop_pods.json)
  echo "=== Pod: $POD (Namespace: $NS) ==="
  kubectl logs "$POD" -n "$NS" --previous --tail=50 2>/dev/null || echo "无法获取previous日志"
  kubectl describe pod "$POD" -n "$NS" | grep -A20 "Events:"
done

# Step 3: 检查Pod资源限制 (20s)
kubectl get pods --all-namespaces -o json | jq '
  .items[] | select(.status.containerStatuses[]?.state.waiting?.reason == "CrashLoopBackOff") |
  {name: .metadata.name, namespace: .metadata.namespace,
   cpu_limit: .spec.containers[0].resources.limits.cpu,
   mem_limit: .spec.containers[0].resources.limits.memory}'

# Step 4: 检查ConfigMap/Secret引用 (20s)
kubectl get pods --all-namespaces -o json | jq '
  .items[] | select(.status.containerStatuses[]?.state.waiting?.reason == "CrashLoopBackOff") |
  .spec.containers[].envFrom[]?.configMapRef?.name' | sort | uniq -c

# Step 5: 检查Deployment更新时间 (10s)
kubectl get deployments --all-namespaces -o wide | grep -E "NAME|$(jq -r '.[].namespace' /tmp/crashloop_pods.json | head -5 | tr '\n' '|' | sed 's/|$//')"
```

**根因判断**:
- 如果 `OOMKilled` 出现频繁 → **根因: 内存不足**
- 如果日志显示配置错误 → **根因: ConfigMap/Secret配置问题**
- 如果 `ImagePullBackOff` → **根因: 镜像拉取失败**
- 如果应用日志显示依赖服务不可达 → **根因: 外部依赖问题**
- 如果最近有Deployment更新 → **根因: 新版本应用bug**

**即时行动**:
1. OOMKilled → 增加Pod内存limit
2. 配置错误 → 检查并修复ConfigMap/Secret
3. 镜像问题 → 检查imagePullSecret和镜像tag
4. 依赖问题 → 检查Service和Endpoints,修复依赖服务
5. 应用bug → 回滚Deployment或修复应用代码

---

### 6.3 Scenario: "集群CPU/Memory过载 + HPA未生效"

**症状**: 集群资源使用率高(>85%), 但Pod Pending, HPA未触发扩容

**诊断剧本**:

```bash
# Step 1: 获取集群资源使用 (10s)
aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName CpuUsage \
  --Dimensions '[{"clusterId":"{{cluster_id}}"}]' \
  --Period 60

aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName MemoryUsage \
  --Dimensions '[{"clusterId":"{{cluster_id}}"}]' \
  --Period 60

# Step 2: 获取Node Pool配置 (10s)
aliyun cs GET /clusters/{{cluster_id}}/nodepools | jq '
  .nodepools[] | {name, nodepool_id, desired_size, min_size, max_size, current_size, state}'

# Step 3: 获取kubeconfig并检查HPA状态 (20s)
aliyun cs GET /k8s/{{cluster_id}}/user_config > /tmp/ack-kubeconfig
export KUBECONFIG=/tmp/ack-kubeconfig

kubectl get hpa --all-namespaces -o wide

# 详细检查HPA状态
kubectl describe hpa -n {{namespace}} {{hpa_name}}

# Step 4: 检查metrics-server状态 (10s)
kubectl get deployment metrics-server -n kube-system -o wide
kubectl get pods -n kube-system -l k8s-app=metrics-server

# Step 5: 检查Pod Pending原因 (20s)
kubectl get pods --all-namespaces --field-selector status.phase=Pending | head -20

kubectl describe pod {{pending_pod_name}} -n {{namespace}} | grep -A10 "Events:"
```

**根因判断**:
- 如果HPA显示 `Desired replicas` > `Current replicas` → **根因: Node Pool已达max_size**
- 如果HPA显示 `Desired replicas` = `Current replicas` → **根因: HPA配置阈值不合理**
- 如果 `metrics-server` Pod异常 → **根因: Metrics Server故障,HPA无法获取指标**
- 如果Node Pool `max_size` = `current_size` → **根因: Node Pool容量上限**
- 如果Pod Pending显示 `Insufficient cpu/memory` → **根因: 节点资源不足**

**即时行动**:
1. Node Pool达到上限 → 扩容Node Pool: `PUT /clusters/{id}/nodepools/{pool_id}` 增加 `max_size`
2. HPA阈值问题 → 调整HPA配置: `kubectl patch hpa ...`
3. Metrics Server故障 → 重启metrics-server Pod或修复配置
4. 立即扩容节点 → `aliyun cs POST /clusters/{id}/nodes --body '{"count": N, ...}'`

---

## 7. Alert Severity Escalation Matrix

| Severity | Condition | Auto-Action | Human Notification | Response Time |
|----------|-----------|-------------|-------------------|---------------|
| **P0-Critical** | Node NotReady > 30%<br>OR Cluster state != running<br>OR Pod CrashLoopBackOff > 50 pods<br>OR PVC Lost affecting critical service | 立即执行诊断工作流<br>自动收集所有相关日志和事件<br>触发节点自动替换(如果配置) | 立即通知运维负责人 + 应用Owner<br>电话/短信/钉钉 | 5 分钟内 |
| **P1-High** | Node NotReady > 10%<br>OR Cluster CPU > 85%<br>OR Cluster Memory > 90%<br>OR Pod CrashLoopBackOff > 20 pods<br>OR Ingress 5xx > 10% | 执行诊断工作流<br>收集性能指标和Pod状态<br>触发HPA(如果配置) | 通知运维负责人<br>企业微信/钉钉 | 15 分钟内 |
| **P2-Medium** | Node NotReady > 1 node<br>OR Cluster CPU > 70%<br>OR Cluster Memory > 75%<br>OR Pod Pending > 10 pods<br>OR Disk usage > 80% | 执行标准检查<br>生成趋势报告<br>建议扩容或优化 | 通知运维人员<br>邮件/工单 | 1 小时内 |
| **P3-Low** | Node CPU > 60%<br>OR Node Memory > 70%<br>OR Pod restartCount > 3<br>OR HPA triggered but recovered | 记录日志<br>纳入日报<br>分析优化机会 | 日报汇总 | 24 小时内 |

---

## 8. Intelligent Recommendations Engine

Based on diagnosis results, Agent should automatically generate the following types of recommendations:

### 8.1 Node Optimization Recommendations

| Finding | Confidence | Recommendation | Priority |
|---------|-----------|----------------|----------|
| Node DiskPressure > 90% | High | 清理未使用镜像: `docker image prune -af`<br>清理日志: `find /var/log -type f -mtime +7 -delete` | P1 |
| Node MemoryPressure | High | 驱逐低QoS Pod<br>调整Pod memory limit<br>扩容Node Pool | P1 |
| Node CPU持续 > 80% | High | 扩容Node Pool<br>启用Cluster Autoscaler<br>调整Pod CPU request | P1 |
| 单节点NotReady反复出现 | Medium | 检查节点硬件健康<br>考虑替换实例 | P2 |
| 节点资源分配不均 | Medium | 启用Descheduler重新平衡Pod分布 | P2 |

### 8.2 Pod/Workload Optimization Recommendations

| Finding | Confidence | Recommendation | Risk |
|---------|-----------|----------------|------|
| Pod OOMKilled频繁 | High | 增加memory limit (基于实际使用+20%冗余)<br>检查应用内存泄漏 | Low |
| Pod CPU throttle | High | 增加CPU limit或优化应用CPU使用 | Low |
| Pod Pending因资源不足 | High | 降低resource request(如果合理)<br>或扩容Node Pool | Medium |
| Pod CrashLoop因配置错误 | High | 修复ConfigMap/Secret配置<br>验证配置项存在性 | Low |
| Pod restartCount高但Running | Medium | 检查livenessProbe配置<br>延长initialDelaySeconds | Low |
| Deployment replicas不足 | High | 调整Deployment replicas<br>或配置HPA | Low |

### 8.3 Cluster Scaling Recommendations

| Finding | Confidence | Recommendation | Cost Impact |
|---------|-----------|----------------|-------------|
| CPU > 80% 持续 7 天 | High | 扩容Node Pool (增加节点数)<br>升级节点规格(更大CPU/Memory) | High |
| Memory > 85% 持续 | High | 扩容Node Pool或升级节点规格 | High |
| Pod Pending常态化 | High | 启用Cluster Autoscaler<br>增加Node Pool max_size | Medium |
| Node Pool利用率 < 30% | Medium | 缩容Node Pool<br>或切换到Spot实例降成本 | Low |
| 单AZ部署风险 | High | 扩展到多AZ Node Pool<br>配置跨可用区调度 | Medium |

### 8.4 Network/Service Optimization Recommendations

| Finding | Confidence | Recommendation | Priority |
|---------|-----------|----------------|----------|
| Endpoints empty | High | 修复Service selector匹配Pod label<br>检查Pod Ready状态 | P1 |
| Ingress 5xx高频 | High | 检查Backend Pod健康<br>优化Ingress timeout配置<br>启用健康检查 | P1 |
| DNS解析慢/失败 | High | 检查CoreDNS Pod数量<br>增加CoreDNS replicas<br>启用NodeLocal DNSCache | P1 |
| NetworkPolicy阻止必要流量 | Medium | 调整NetworkPolicy规则<br>添加必要允许规则 | P2 |
| 跨Namespace通信失败 | Medium | 检查Service配置<br>调整NetworkPolicy跨Namespace规则 | P2 |

### 8.5 Storage Optimization Recommendations

| Finding | Confidence | Recommendation | Risk |
|---------|-----------|----------------|------|
| PVC Pending因无PV | High | 创建PV或配置StorageClass动态创建 | Medium |
| PVC挂载失败 | High | 检查节点与存储Zone一致性<br>修复Provisioner配置 | Low |
| 云盘使用率 > 90% | High | 扩容云盘: ResizeDisk<br>清理数据或归档 | Medium |
| PV Released未回收 | Medium | 修改PV reclaimPolicy为Delete<br>或手动回收PV | Low |

---

## 9. Agent Execution Guidelines for Diagnosis

When user reports an alert or performance issue, Agent MUST follow this execution order:

1. **Acknowledge** the alert and confirm ClusterId
2. **Triage** — get cluster status and basic info (DescribeClusterDetail)
3. **Correlate** — get multi-dimensional metrics based on alert type
4. **Deep-dive** — execute Kubernetes-specific diagnostics (kubectl commands)
5. **Synthesize** — apply correlation matrix to identify root cause
6. **Report** — output structured diagnosis report (Section 5.2 template)
7. **Recommend** — provide prioritized, actionable recommendations
8. **Verify** — if user executes recommendation, verify improvement

> **IMPORTANT**: Agent MUST NOT jump to conclusions without collecting sufficient evidence. Always collect at least 3 data points before declaring a root cause.

---

## 10. Cross-Skill Delegation Protocol

| Diagnosis Finding | Delegate To | Purpose |
|-------------------|-------------|---------|
| ECS instance Status != Running | `alicloud-ecs-ops` | ECS实例故障修复 |
| ECS disk usage > 90% | `alicloud-ecs-ops` | 磁盘扩容或清理 |
| VPC network unreachable | `alicloud-vpc-ops` | VPC路由/安全组诊断 |
| SLB health check abnormal | `alicloud-slb-ops` | SLB配置和健康检查诊断 |
| Cloud disk resize needed | `alicloud-ecs-ops` | 云盘扩容操作 |
| CMS alert configuration | `alicloud-cms-ops` | 告警规则配置和查询 |
| RDS dependency failure | `alicloud-rds-ops` | 数据库连接和性能诊断 |

---

## 11. Diagnostic Script Library

### 11.1 Full Cluster Health Check Script

```bash
#!/bin/bash
# ack-full-health-check.sh
# Usage: ./ack-full-health-check.sh <ClusterId> <RegionId>

CLUSTER_ID="$1"
REGION="$2"
REPORT_FILE="/tmp/ack_health_${CLUSTER_ID}_$(date +%Y%m%d_%H%M%S).json"

echo "=== ACK Cluster Full Health Check ==="
echo "Cluster: $CLUSTER_ID"
echo "Region: $REGION"
echo "Report: $REPORT_FILE"
echo ""

# Phase 1: Cluster state
CLUSTER_STATE=$(aliyun cs GET /clusters/$CLUSTER_ID | jq -r '.state')
CLUSTER_VERSION=$(aliyun cs GET /clusters/$CLUSTER_ID | jq -r '.current_version')
echo "[Phase 1] Cluster State: $CLUSTER_STATE, Version: $CLUSTER_VERSION"

# Phase 2: Node health
NODES=$(aliyun cs GET /clusters/$CLUSTER_ID/nodes)
READY_COUNT=$(echo "$NODES" | jq '[.nodes[] | select(.node_status == "Ready")] | length')
TOTAL_COUNT=$(echo "$NODES" | jq '.nodes | length')
NOTREADY_COUNT=$((TOTAL_COUNT - READY_COUNT))
echo "[Phase 2] Nodes: $READY_COUNT/$TOTAL_COUNT Ready ($NOTREADY_COUNT NotReady)"

# Phase 3: Pod health (via kubeconfig)
aliyun cs GET /k8s/$CLUSTER_ID/user_config > /tmp/ack-kubeconfig_$CLUSTER_ID
export KUBECONFIG=/tmp/ack-kubeconfig_$CLUSTER_ID

POD_RUNNING=$(kubectl get pods --all-namespaces --field-selector status.phase=Running -o json | jq '.items | length')
POD_PENDING=$(kubectl get pods --all-namespaces --field-selector status.phase=Pending -o json | jq '.items | length')
POD_FAILED=$(kubectl get pods --all-namespaces --field-selector status.phase=Failed -o json | jq '.items | length')
POD_CRASHLOOP=$(kubectl get pods --all-namespaces -o json | jq '[.items[] | select(.status.containerStatuses[]?.state.waiting?.reason == "CrashLoopBackOff")] | length')
echo "[Phase 3] Pods: Running=$POD_RUNNING, Pending=$POD_PENDING, Failed=$POD_FAILED, CrashLoop=$POD_CRASHLOOP"

# Phase 4: Resource metrics
START_TIME=$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)

CPU_USAGE=$(aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName CpuUsage \
  --Dimensions "[{\"clusterId\":\"$CLUSTER_ID\"}]" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --Period 60 | jq -r '.Datapoints[-1].Average // "N/A"')

MEM_USAGE=$(aliyun cms DescribeMetricList \
  --Namespace acs_k8s_dashboard \
  --MetricName MemoryUsage \
  --Dimensions "[{\"clusterId\":\"$CLUSTER_ID\"}]" \
  --StartTime "$START_TIME" \
  --EndTime "$END_TIME" \
  --Period 60 | jq -r '.Datapoints[-1].Average // "N/A"')

echo "[Phase 4] Metrics: CPU=${CPU_USAGE}%, Memory=${MEM_USAGE}%"

# Phase 5: Addon status
ADDONS=$(aliyun cs GET /clusters/$CLUSTER_ID/addons 2>/dev/null || echo '{"addons":[]}')
ADDON_ACTIVE=$(echo "$ADDONS" | jq '[.addons[] | select(.state == "active")] | length')
ADDON_TOTAL=$(echo "$ADDONS" | jq '.addons | length')
echo "[Phase 5] Addons: $ADDON_ACTIVE/$ADDON_TOTAL Active"

# Generate report
jq -n \
  --arg cluster_id "$CLUSTER_ID" \
  --arg state "$CLUSTER_STATE" \
  --arg version "$CLUSTER_VERSION" \
  --argjson ready "$READY_COUNT" \
  --argjson total "$TOTAL_COUNT" \
  --argjson notready "$NOTREADY_COUNT" \
  --argjson running "$POD_RUNNING" \
  --argjson pending "$POD_PENDING" \
  --argjson failed "$POD_FAILED" \
  --argjson crashloop "$POD_CRASHLOOP" \
  --arg cpu "$CPU_USAGE" \
  --arg mem "$MEM_USAGE" \
  --argjson addon_active "$ADDON_ACTIVE" \
  --argjson addon_total "$ADDON_TOTAL" \
  --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{
    cluster_id: $cluster_id,
    cluster_state: $state,
    k8s_version: $version,
    nodes: {ready: $ready, total: $total, notready: $notready},
    pods: {running: $running, pending: $pending, failed: $failed, crashloop: $crashloop},
    metrics: {cpu_usage: $cpu, memory_usage: $mem},
    addons: {active: $addon_active, total: $addon_total},
    timestamp: $timestamp
  }' > "$REPORT_FILE"

echo ""
echo "=== Health Score Calculation ==="
SCORE=100

# Deduct for NotReady nodes
if [ "$NOTREADY_COUNT" -gt 0 ]; then
  NODE_PENALTY=$((NOTREADY_COUNT * 10))
  SCORE=$((SCORE - NODE_PENALTY))
fi

# Deduct for CrashLoop pods
if [ "$POD_CRASHLOOP" -gt 5 ]; then
  POD_PENALTY=$((POD_CRASHLOOP * 2))
  SCORE=$((SCORE - POD_PENALTY))
fi

# Deduct for high resource usage
CPU_INT=${CPU_USAGE%.*}
MEM_INT=${MEM_USAGE%.*}
if [ "$CPU_INT" -gt 85 ]; then
  SCORE=$((SCORE - 15))
elif [ "$CPU_INT" -gt 70 ]; then
  SCORE=$((SCORE - 5))
fi
if [ "$MEM_INT" -gt 90 ]; then
  SCORE=$((SCORE - 15))
elif [ "$MEM_INT" -gt 75 ]; then
  SCORE=$((SCORE - 5))
fi

# Deduct for cluster state
if [ "$CLUSTER_STATE" != "running" ]; then
  SCORE=$((SCORE - 50))
fi

echo "Health Score: $SCORE/100"

if [ "$SCORE" -ge 90 ]; then
  echo "Status: HEALTHY"
elif [ "$SCORE" -ge 70 ]; then
  echo "Status: WARNING - Review recommended"
elif [ "$SCORE" -ge 50 ]; then
  echo "Status: CRITICAL - Immediate action required"
else
  echo "Status: SEVERE - Urgent intervention needed"
fi

echo ""
echo "Report saved to: $REPORT_FILE"

# Cleanup
rm -f /tmp/ack-kubeconfig_$CLUSTER_ID
```

### 11.2 Pod Deep Diagnosis Script

```bash
#!/bin/bash
# ack-pod-diagnosis.sh
# Usage: ./ack-pod-diagnosis.sh <ClusterId> <PodName> <Namespace>

CLUSTER_ID="$1"
POD_NAME="$2"
NAMESPACE="$3"

echo "=== Pod Deep Diagnosis ==="
echo "Pod: $POD_NAME (Namespace: $NAMESPACE)"

# Get kubeconfig
aliyun cs GET /k8s/$CLUSTER_ID/user_config > /tmp/ack-kubeconfig
export KUBECONFIG=/tmp/ack-kubeconfig

echo ""
echo "[1] Pod Status"
kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o wide

echo ""
echo "[2] Pod Conditions"
kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.conditions}' | jq '.'echo ""
echo "[3] Container Statuses"
kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o json | jq '.status.containerStatuses[]'

echo ""
echo "[4] Resource Requests/Limits"
kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o json | jq '.spec.containers[].resources'

echo ""
echo "[5] Recent Events"
kubectl describe pod "$POD_NAME" -n "$NAMESPACE" | grep -A30 "Events:"echo ""
echo "[6] Current Logs (last 50 lines)"
kubectl logs "$POD_NAME" -n "$NAMESPACE" --tail=50 2>/dev/null || echo "Cannot get logs - container may not be running"

echo ""
echo "[7] Previous Logs (if restarted)"
kubectl logs "$POD_NAME" -n "$NAMESPACE" --previous --tail=50 2>/dev/null || echo "No previous logs available"

echo ""
echo "[8] Network Test"
POD_IP=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath='{.status.podIP}')
echo "Pod IP: $POD_IP"

echo ""
echo "[9] ConfigMap/Secret References"
kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o json | jq '.spec.containers[].envFrom[]?.configMapRef?.name'
kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o json | jq '.spec.containers[].envFrom[]?.secretRef?.name'
kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o json | jq '.spec.containers[].volumeMounts[]'

rm -f /tmp/ack-kubeconfig
```