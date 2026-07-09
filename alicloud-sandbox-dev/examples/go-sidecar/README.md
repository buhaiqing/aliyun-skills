# Go Sidecar 最小可运行示例

## 快速开始

```bash
# 1. 初始化项目
mkdir go-sidecar-example && cd go-sidecar-example
go mod init go-sidecar-example

# 2. 安装依赖
go get go.uber.org/zap@latest
go get github.com/prometheus/client_golang/prometheus/promhttp@latest

# 3. 复制完整的实现代码
# 参考 ../../references/go-implementation.md 中的完整代码
# 按照以下目录结构组织：
#
# go-sidecar-example/
# ├── cmd/
# │   └── sidecar/
# │       └── main.go
# ├── internal/
# │   ├── auth/
# │   │   ├── signer.go
# │   │   └── credential.go
# │   ├── config/
# │   │   └── config.go
# │   └── server/
# │       └── server.go
# ├── go.mod
# └── go.sum

# 4. 设置环境变量
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-ak"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-sk"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
export ALIBABA_CLOUD_ACCOUNT_ID="your-account-id"

# 5. 编译运行
go build -o sandbox-sidecar ./cmd/sidecar
./sandbox-sidecar

# 6. 测试健康检查
curl http://localhost:8080/healthz
```

## 测试端点

```bash
# 健康检查
curl http://localhost:8080/healthz

# Prometheus 指标
curl http://localhost:8080/metrics

# 创建模板（需要有效的 AK/SK）
curl -X POST http://localhost:8080/api/sandbox/v1/templates \
  -H "Content-Type: application/json" \
  -d '{
    "templateName": "test-template",
    "cpu": 1,
    "memory": 1024
  }'
```

## 注意事项

1. 这是最小示例，生产环境需要添加：
   - 速率限制中间件
   - 熔断器
   - 更完善的错误处理
   - 日志脱敏
   - OpenTelemetry 链路追踪

2. 完整的实现代码请参考 [references/go-implementation.md](../../references/go-implementation.md)
