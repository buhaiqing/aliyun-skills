# Python 实现 Sidecar 代理应用

> **目的**: 如何用 Python 实现 FC Sandbox Sidecar 代理应用。适用于快速原型验证和对性能要求不高的场景。

## 1. 项目结构

```
sandbox-sidecar/
├── app/
│   ├── __init__.py
│   ├── main.py              # 应用入口 (FastAPI)
│   ├── auth/
│   │   ├── __init__.py
│   │   └── signer.py        # 签名模块
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py      # 配置管理
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── control.py       # 控制面路由
│   │   └── data.py          # 数据面路由
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── proxy.py         # 代理中间件
│   └── models/
│       ├── __init__.py
│       └── types.py         # 数据模型
├── requirements.txt
├── Dockerfile
└── config.yaml
```

## 2. 依赖安装

```bash
mkdir sandbox-sidecar-py && cd sandbox-sidecar-py
python3 -m venv venv && source venv/bin/activate

cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn==0.24.0
httpx==0.25.2
httpx-ws==0.6.0
pyyaml==6.0.1
websockets==12.0
prometheus-client==0.19.0
structlog==23.2.0
pydantic==2.5.0
pydantic-settings==2.1.0
EOF

pip install -r requirements.txt
```

## 3. 核心实现

### 3.1 配置管理 (`app/config/settings.py`)

```python
import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8080
    
    # 阿里云凭据
    access_key_id: str = ""
    access_key_secret: str = ""
    region_id: str = "cn-hangzhou"
    account_id: str = ""
    
    # 端点配置
    control_endpoint_template: str = "agentrun.{region}.aliyuncs.com"
    data_endpoint_template: str = "{account}.agentrun-data.{region}.aliyuncs.com"
    
    # 弹性配置
    rate_limit_rps: int = 50
    max_retries: int = 3
    
    model_config = {"env_prefix": "ALIBABA_CLOUD_"}

    @property
    def control_endpoint(self) -> str:
        return self.control_endpoint_template.replace("{region}", self.region_id)
    
    @property
    def data_endpoint(self) -> str:
        return self.data_endpoint_template.replace("{account}", self.account_id).replace("{region}", self.region_id)

settings = Settings()
```

### 3.2 签名模块 (`app/auth/signer.py`)

```python
import hashlib
import hmac
import datetime
from typing import Dict, Tuple

class AgentRunSigner:
    def __init__(self, access_key_id: str, access_key_secret: str, region: str, service: str = "agentrun"):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.region = region
        self.service = service

    def _sha256_hex(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _hmac_sha256(self, key: bytes, data: str) -> bytes:
        return hmac.new(key, data.encode('utf-8'), hashlib.sha256).digest()

    def _derive_signing_key(self, date: str) -> bytes:
        k_secret = ("ACS3" + self.access_key_secret).encode('utf-8')
        k_date = self._hmac_sha256(k_secret, date)
        k_region = self._hmac_sha256(k_date, self.region)
        k_service = self._hmac_sha256(k_region, self.service)
        return self._hmac_sha256(k_service, "aliyun_v4_request")

    def sign(self, method: str, path: str, query: str, body: bytes, host: str) -> Dict[str, str]:
        now = datetime.datetime.utcnow()
        date_time = now.strftime("%Y%m%dT%H%M%SZ")
        date = now.strftime("%Y%m%d")

        body_hash = self._sha256_hex(body)
        
        # Headers (must be lowercase, sorted)
        headers_dict = {
            "content-type": "application/json",
            "host": host,
            "x-acs-content-sha256": body_hash,
            "x-acs-date": date_time,
        }
        
        sorted_keys = sorted(headers_dict.keys())
        canonical_headers = "\n".join(f"{k}:{headers_dict[k].strip()}" for k in sorted_keys) + "\n"
        signed_headers = ";".join(sorted_keys)
        
        # Canonical Request
        canonical_request = (
            f"{method}\n{path}\n{query}\n{canonical_headers}\n{signed_headers}\n{body_hash}"
        )
        
        cr_hash = self._sha256_hex(canonical_request.encode('utf-8'))
        credential_scope = f"{date}/{self.region}/{self.service}/aliyun_v4_request"
        string_to_sign = f"ACS3-HMAC-SHA256\n{date_time}\n{credential_scope}\n{cr_hash}"
        
        signing_key = self._derive_signing_key(date)
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        
        authorization = (
            f"ACS3-HMAC-SHA256 "
            f"Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )
        
        return {
            "Authorization": authorization,
            "X-Acs-Date": date_time,
            "X-Acs-Content-Sha256": body_hash,
        }
```

### 3.3 主应用 (`app/main.py`)

```python
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from typing import Dict, Any
import httpx
import structlog

from app.config.settings import settings
from app.auth.signer import AgentRunSigner

logger = structlog.get_logger()

app = FastAPI(title="Sandbox Sidecar Proxy", version="1.0.0")
signer = AgentRunSigner(settings.access_key_id, settings.access_key_secret, settings.region_id)

async def proxy_request(
    method: str,
    target_url: str,
    body: bytes,
    headers: Dict[str, str],
    extra_headers: Dict[str, str] = None,
) -> Response:
    """通用代理函数：签名 + 转发 + 返回响应"""
    from urllib.parse import urlparse
    host = urlparse(target_url).netloc
    
    auth_headers = signer.sign(method, urlparse(target_url).path, urlparse(target_url).query, body, host)
    
    all_headers = {**headers, **auth_headers, "X-Acs-Parent-Id": settings.account_id}
    if extra_headers:
        all_headers.update(extra_headers)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=method,
                url=target_url,
                content=body,
                headers=all_headers,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers={
                    "Content-Type": resp.headers.get("Content-Type", "application/json"),
                },
            )
        except httpx.RequestError as e:
            logger.error("proxy_request_failed", error=str(e))
            return JSONResponse(
                status_code=502,
                content={"error": f"upstream error: {str(e)}"},
            )

# ===== 控制面路由 =====

@app.post("/api/sandbox/v1/templates")
async def create_template(request: Request):
    body = await request.body()
    target = f"https://{settings.control_endpoint}/2025-09-10/templates"
    return await proxy_request("POST", target, body, dict(request.headers))

@app.delete("/api/sandbox/v1/templates/{template_id}")
async def delete_template(template_id: str):
    body = b""
    target = f"https://{settings.control_endpoint}/2025-09-10/templates/{template_id}"
    return await proxy_request("DELETE", target, body, {})

# ===== Sandbox 实例管理 =====

@app.post("/api/sandbox/v1/sandboxes")
async def create_sandbox(request: Request):
    body = await request.body()
    target = f"https://{settings.control_endpoint}/2025-09-10/sandboxes"
    return await proxy_request("POST", target, body, dict(request.headers))

@app.post("/api/sandbox/v1/sandboxes/{sandbox_id}/stop")
async def stop_sandbox(sandbox_id: str):
    body = b""
    target = f"https://{settings.control_endpoint}/2025-09-10/sandboxes/{sandbox_id}/stop"
    return await proxy_request("POST", target, body, {})

@app.delete("/api/sandbox/v1/sandboxes/{sandbox_id}")
async def delete_sandbox(sandbox_id: str):
    body = b""
    target = f"https://{settings.control_endpoint}/2025-09-10/sandboxes/{sandbox_id}"
    return await proxy_request("DELETE", target, body, {})

# ===== 数据面路由 =====

@app.post("/api/sandbox/v1/sandboxes/{sandbox_id}/execute")
async def execute_code(sandbox_id: str, request: Request):
    body = await request.body()
    target = f"https://{settings.data_endpoint}/sandboxes/{sandbox_id}/contexts/execute"
    return await proxy_request("POST", target, body, dict(request.headers))

@app.get("/api/sandbox/v1/sandboxes/{sandbox_id}/health")
async def health_check(sandbox_id: str):
    body = b""
    target = f"https://{settings.data_endpoint}/sandboxes/{sandbox_id}/health"
    return await proxy_request("GET", target, body, {})

@app.get("/api/sandbox/v1/sandboxes/{sandbox_id}/files")
async def read_file(sandbox_id: str, path: str = ""):
    body = b""
    target = f"https://{settings.data_endpoint}/sandboxes/{sandbox_id}/files"
    if path:
        target += f"?path={path}"
    return await proxy_request("GET", target, body, {})

@app.post("/api/sandbox/v1/sandboxes/{sandbox_id}/files")
async def write_file(sandbox_id: str, request: Request):
    body = await request.body()
    target = f"https://{settings.data_endpoint}/sandboxes/{sandbox_id}/files"
    return await proxy_request("POST", target, body, dict(request.headers))

# ===== 健康与观测 =====

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "sandbox-sidecar"}

@app.get("/metrics")
async def metrics():
    from prometheus_client import generate_latest
    return Response(content=generate_latest(), media_type="text/plain")

# ===== 启动 =====

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
```

### 3.4 Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
```

## 4. 运行

```bash
# 设置环境变量
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-ak"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-sk"
export ALIBABA_CLOUD_REGION_ID="cn-hangzhou"
export ALIBABA_CLOUD_ACCOUNT_ID="your-account-id"

# 直接运行
python -m app.main

# 或使用 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

## 5. Go vs Python 对比

| 维度 | Go | Python (FastAPI) |
|---|---|---|
| **性能** | 高（原生并发，低延迟） | 中（异步 IO，但 GIL 影响） |
| **部署** | 单二进制，无需运行时 | 需要 Python 环境和依赖 |
| **WebSocket** | 标准库支持 | 需要额外库 (websockets) |
| **签名实现** | 标准库 crypto | 标准库 hashlib + hmac |
| **开发速度** | 中等（类型检查严格） | 快（动态类型，FastAPI 成熟） |
| **镜像大小** | <20MB (scratch/alpine) | ~150MB (python:3.9-slim) |
| **适用场景** | 生产部署，高频调用 | 快速原型，低频场景 |

## 6. 关键注意事项

1. **httpx 自动处理 Body 流**：签名前必须先读取 `await request.body()`，然后再传给签名函数
2. **FastAPI 异步并发**：使用 `async/await` 实现非阻塞代理，适合 I/O 密集型场景
3. **worker 数量**：建议 `--workers = 2 * CPU核心数 + 1`
4. **日志**：使用 structlog 提供结构化日志，便于与 ELK/Loki 集成
5. **超时**：httpx 默认无超时，必须显式设置 `timeout=30.0`（数据面网关硬 30 秒限制）
