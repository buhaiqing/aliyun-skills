# Python Sidecar 最小可运行示例

## 快速开始

```bash
# 1. 创建项目
mkdir python-sidecar-example && cd python-sidecar-example
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install fastapi uvicorn httpx httpx-ws pyyaml prometheus-client structlog pydantic pydantic-settings

# 3. 复制完整的实现代码
# 参考 ../../references/python-implementation.md 中的完整代码
# 按照以下目录结构组织：
#
# python-sidecar-example/
# ├── app/
# │   ├── __init__.py
# │   ├── main.py
# │   ├── auth/
# │   │   ├── __init__.py
# │   │   └── signer.py
# │   └── config/
# │       ├── __init__.py
# │       └── settings.py
# ├── requirements.txt
# └── Dockerfile

# 4. 设置环境变量
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-ak"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-sk"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
export ALIBABA_CLOUD_ACCOUNT_ID="your-account-id"

# 5. 运行应用
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2

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
   - WebSocket 连接池管理

2. 完整的实现代码请参考 [references/python-implementation.md](../../references/python-implementation.md)

3. WebSocket TTY 功能需要额外安装 `httpx-ws` 库
