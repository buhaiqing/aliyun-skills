# API & SDK — Alibaba Cloud AgentRun

## Overview

AgentRun 提供两种调用方式：

| 方式 | 适用场景 | 特点 |
|------|----------|------|
| **HTTP API (ACS3)** | 底层资源管理、精细控制 | 需手动签名，功能完整 |
| **AgentRun CLI (`ar`)** | 终端交互、CI/CD、脚本自动化 | 预置签名，使用便捷 |

---

## AgentRun CLI

### 安装

```bash
# 方式一：预编译二进制（推荐）
curl -fsSL https://raw.githubusercontent.com/Serverless-Devs/agentrun-cli/main/scripts/install.sh | sh

# 方式二：PyPI
pip install agentrun-cli

# 验证
ar --version
```

### 配置

```bash
# 设置默认凭证
ar config set access_key_id     $ALIBABA_CLOUD_ACCESS_KEY_ID
ar config set access_key_secret $ALIBABA_CLOUD_ACCESS_KEY_SECRET
ar config set account_id        $ALIBABA_CLOUD_ACCOUNT_ID
ar config set region            $ALIBABA_CLOUD_REGION_ID

# 多环境支持
ar config set region cn-shanghai --profile staging
ar --profile staging template list
```

### CLI 命令映射表

| 操作目标 | CLI 命令 | HTTP API 对应 |
|----------|----------|---------------|
| **Template 管理** | | |
| 创建 Template | `ar template create` | `POST /templates` |
| 查询 Template | `ar template get <name>` | `GET /templates/{name}` |
| 列出 Templates | `ar template list` | `GET /templates` |
| 更新 Template | `ar template update <name>` | `PUT /templates/{name}` |
| 删除 Template | `ar template delete <name>` | `DELETE /templates/{name}` |
| **Sandbox 管理** | | |
| 创建 Sandbox | `ar sandbox create` | `POST /sandboxes` |
| 查询 Sandbox | `ar sandbox get <id>` | `GET /sandboxes/{id}` |
| 列出 Sandboxes | `ar sandbox list` | `GET /sandboxes` |
| 停止 Sandbox | `ar sandbox stop <id>` | `POST /sandboxes/{id}/stop` |
| 删除 Sandbox | `ar sandbox delete <id>` | `DELETE /sandboxes/{id}` |
| 暂停 Sandbox | `ar sandbox pause <id>` | `POST /sandboxes/{id}/pause` |
| 恢复 Sandbox | `ar sandbox resume <id>` | `POST /sandboxes/{id}/resume` |
| **代码执行** | | |
| 执行代码 | `ar sandbox exec <id>` | `POST /contexts/execute` |
| 执行命令 | `ar sandbox run <id> --command` | `POST /processes/cmd` |
| 交互式终端 | `ar sandbox tty <id>` | `WebSocket /processes/tty` |
| **文件操作** | | |
| 上传文件 | `ar sandbox upload <id>` | `POST /filesystem/upload` |
| 下载文件 | `ar sandbox download <id>` | `GET /filesystem/download` |
| 列出文件 | `ar sandbox ls <id>` | `GET /filesystem` |

---

## HTTP API (ACS3-HMAC-SHA256)

### 服务端点

| 平面 | 端点格式 |
|------|----------|
| Control Plane | `https://agentrun.{region}.aliyuncs.com/2025-09-10` |
| Data Plane | `https://{account}.agentrun-data.{region}.aliyuncs.com` |

### 签名实现

参考 [api-signing.md](api-signing.md) 获取完整的 ACS3-HMAC-SHA256 签名实现。

快速示例：

```python
# assets/code-snippets/sign.py
import hashlib, hmac, datetime

def sign_request(method, host, path, body, ak, sk, region):
    now = datetime.datetime.utcnow()
    date_time = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    headers = f"content-type:application/json\nhost:{host}\nx-acs-content-sha256:{body_hash}\nx-acs-date:{date_time}\n"
    signed_headers = "content-type;host;x-acs-content-sha256;x-acs-date"
    
    canonical = f"{method}\n{path}\n\n{headers}\n{signed_headers}\n{body_hash}"
    scope = f"{date}/{region}/agentrun/aliyun_v4_request"
    string_to_sign = f"ACS3-HMAC-SHA256\n{date_time}\n{scope}\n{hashlib.sha256(canonical.encode()).hexdigest()}"
    
    # 签名密钥派生
    k = hmac.new(("ACS3" + sk).encode(), date.encode(), hashlib.sha256).digest()
    k = hmac.new(k, region.encode(), hashlib.sha256).digest()
    k = hmac.new(k, b"agentrun", hashlib.sha256).digest()
    k = hmac.new(k, b"aliyun_v4_request", hashlib.sha256).digest()
    
    signature = hmac.new(k, string_to_sign.encode(), hashlib.sha256).hexdigest()
    return f"ACS3-HMAC-SHA256 Credential={ak}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
```

---

## 使用建议

### 何时使用 CLI

- ✅ 终端交互式操作
- ✅ CI/CD 流水线脚本
- ✅ 快速原型开发
- ✅ 本地开发和测试

### 何时使用 HTTP API

- ✅ 需要自定义 HTTP 客户端
- ✅ 嵌入现有应用程序
- ✅ 需要完整控制请求/响应
- ✅ 使用非标准运行时环境

### 混合使用示例

```bash
# Step 1: 使用 CLI 创建 Template
ar template create --name my-template --cpu 2 --memory 4096

# Step 2: 使用 CLI 创建 Sandbox
SANDBOX_ID=$(ar sandbox create --template my-template --output json | jq -r '.sandboxId')

# Step 3: 使用 HTTP API 执行复杂代码（需自定义请求头）
curl -X POST "https://${ACCOUNT}.agentrun-data.${REGION}.aliyuncs.com/sandboxes/${SANDBOX_ID}/contexts/execute" \
  -H "Authorization: $(python3 sign.py)" \
  -d '{"language":"python","code":"print(1+1)"}'
```

---

## 退出码（CLI）

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 资源不存在或进入失败态 |
| 2 | 参数错误 |
| 3 | 认证或权限失败 |
| 4 | 服务端错误或请求超时 |
| 5 | Runtime 操作失败 |
| 6 | 轮询超时 |
| 130 | 用户中断 |

---

## 参考链接

- [AgentRun CLI 官方文档](https://help.aliyun.com/zh/functioncompute/use-the-agentrun-cli-to-manage-agentrun-in-terminals-and-ci-pipelines)
- [API Reference](api-reference.md)
- [API Signing Guide](api-signing.md)
