# 部署指南

> **目的**: 如何将 FC Sandbox Sidecar 代理部署到不同环境（Sidecar 模式、独立 Deployment、FC 环境）。

## 1. 部署模式对比

| 模式 | 说明 | 适用场景 | 资源开销 |
|---|---|---|---|
| **Sidecar (同 Pod)** | 每个业务 Pod 一个 Sidecar 容器 | K8s 集群，高频调用 | ~50MB/实例 |
| **独立 Deployment** | 集中式服务，多 Pod 共享 | FC 环境，低频调用 | ~50MB/实例，可复用 |
| **DaemonSet** | 每个 K8s 节点一个实例 | 节点级服务共享 | 1 实例/节点 |

**推荐**: 对于低频场景 + FC 环境 → **独立 Deployment**。

## 2. Docker 镜像构建

### 2.1 Go Sidecar Dockerfile

```dockerfile
# 多阶段构建
FROM golang:1.21-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /sandbox-sidecar ./cmd/sidecar

# 最终镜像
FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata
COPY --from=builder /sandbox-sidecar /usr/local/bin/sandbox-sidecar
RUN addgroup -g 1001 sidecar && adduser -u 1001 -G sidecar -s /bin/sh -D sidecar
USER sidecar
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/sandbox-sidecar"]
```

### 2.2 构建命令

```bash
# 本地构建（替换为您的镜像仓库地址）
docker build -t <your-registry>/sandbox-sidecar:v1.0.0 .
docker push <your-registry>/sandbox-sidecar:v1.0.0
```

## 3. K8s 独立 Deployment 部署

### 3.1 Deployment + Service 配置

```yaml
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sandbox-sidecar
  namespace: sandbox-proxy-system
  labels:
    app: sandbox-sidecar
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sandbox-sidecar
  template:
    metadata:
      labels:
        app: sandbox-sidecar
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      containers:
        - name: sandbox-sidecar
          image: <your-registry>/sandbox-sidecar:v1.0.0
          ports:
            - containerPort: 8080
              name: http
            - containerPort: 9090
              name: metrics
          env:
            - name: ALIBABA_CLOUD_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: aliyun-credentials
                  key: access-key-id
            - name: ALIBABA_CLOUD_ACCESS_KEY_SECRET
              valueFrom:
                secretKeyRef:
                  name: aliyun-credentials
                  key: access-key-secret
            - name: ALIBABA_CLOUD_REGION_ID
              value: "cn-hangzhou"
            - name: ALIBABA_CLOUD_ACCOUNT_ID
              valueFrom:
                secretKeyRef:
                  name: aliyun-credentials
                  key: account-id
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              cpu: "200m"
              memory: "256Mi"
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 30

---
apiVersion: v1
kind: Service
metadata:
  name: sandbox-sidecar-service
  namespace: sandbox-proxy-system
spec:
  selector:
    app: sandbox-sidecar
  ports:
    - name: http
      port: 8080
      targetPort: 8080
      protocol: TCP
    - name: metrics
      port: 9090
      targetPort: 9090
      protocol: TCP

---
apiVersion: v1
kind: Secret
metadata:
  name: aliyun-credentials
  namespace: sandbox-proxy-system
type: Opaque
data:
  # 使用 base64 编码的值，生产环境建议使用 External Secrets Operator + KMS
  access-key-id: <base64(AK)>
  access-key-secret: <base64(SK)>
  account-id: <base64(AccountID)>
```

### 3.2 HPA 自动扩缩容

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: sandbox-sidecar-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: sandbox-sidecar
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## 4. FC 环境部署

### 4.1 Function Compute 自定义容器

```yaml
# serverless-devs 配置 (s.yaml)
edition: 3.0.0
name: sandbox-sidecar-fc
access: default

vars:
  region: cn-hangzhou
  service:
    name: agentrun-services

resources:
  sandbox-sidecar:
    component: fc3
    props:
      region: ${vars.region}
      functionName: sandbox-sidecar
      runtime: custom-container
      description: FC Sandbox Sidecar Proxy
      memorySize: 512
      timeout: 600  # 6 小时最大超时
      diskSize: 512
      instanceConcurrency: 100
      cpu: 1
      customContainerConfig:
        image: <your-registry>/sandbox-sidecar:v1.0.0
        command: '["/usr/local/bin/sandbox-sidecar"]'
        port: 8080
      environmentVariables:
        ALIBABA_CLOUD_REGION_ID: ${vars.region}
        ALIBABA_CLOUD_ACCOUNT_ID: ${env.ACCOUNT_ID}
      triggers:
        - triggerName: http-trigger
          triggerType: http
          triggerConfig:
            authType: anonymous
            methods:
              - GET
              - POST
              - DELETE
```

## 5. 网络策略

### 5.1 NetworkPolicy (K8s)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sandbox-sidecar-network
  namespace: sandbox-proxy-system
spec:
  podSelector:
    matchLabels:
      app: sandbox-sidecar
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # 仅允许业务 Pod 访问
    - from:
        - namespaceSelector:
            matchLabels:
              name: business-namespace
      ports:
        - port: 8080
  egress:
    # 仅允许访问阿里云 AgentRun API
    - to:
        # 控制面
      - ipBlock:
          cidr: 0.0.0.0/0
      ports:
        - port: 443
```

## 6. 资源规划

| 配置项 | 最小值 | 推荐值 | 说明 |
|---|---|---|---|
| CPU Request | 50m | 100m | 签名和代理计算 |
| Memory Request | 64Mi | 128Mi | Go runtime + 连接池 |
| CPU Limit | 200m | 500m | 突发场景 |
| Memory Limit | 256Mi | 512Mi | WebSocket 连接多时 |
| Replicas | 2 | 3-5 | 高可用 + 负载分担 |

## 7. 滚动更新策略

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

## 8. 健康检查

| 探针 | 端点 | 间隔 | 超时 | 阈值 |
|---|---|---|---|---|
| **Readiness** | `/healthz` | 10s | 5s | 1/3 |
| **Liveness** | `/healthz` | 30s | 10s | 3/3 |

## 9. 部署验证

```bash
# 1. 验证 Pod 运行状态
kubectl get pods -n sandbox-proxy-system -l app=sandbox-sidecar

# 2. 验证健康检查
kubectl exec -it <pod-name> -- curl -s http://localhost:8080/healthz
# 预期: {"status":"ok","service":"sandbox-sidecar"}

# 3. 验证 Sidecar 可以代理请求
curl -X POST http://<sidecar-service>.sandbox-proxy-system.svc.cluster.local:8080/api/sandbox/v1/templates \
  -H "Content-Type: application/json" \
  -d '{"templateName":"test","cpu":1,"memory":1024}'
```

## 10. 故障排查

| 问题 | 排查步骤 |
|---|---|
| Pod 无法启动 | `kubectl describe pod <name>`，检查 Secret 是否存在 |
| 侧车无法连接上游 | 检查网络策略、DNS 解析、AK/SK 有效性 |
| 签名失败 | 查看 Sidecar 日志中的 signing error，对照 auth-signing.md |
| WebSocket 断开 | 检查心跳间隔，确认客户端每 30 秒发送 ping |
| 内存溢出 | 检查 WebSocket 连接泄漏，确认连接计数是否下降 |
